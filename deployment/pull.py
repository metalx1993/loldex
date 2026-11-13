"""Credential-free SiteGround pull publisher for the reviewed public repository.

Runs trusted installed publisher code, never code from the fetched checkout.
No cron is installed or enabled by this module. Two independent schedules (GitHub
verified data refresh and host publication) may run at different times safely.
"""
from pathlib import Path
import configparser
import stat
import os
import re
import subprocess

from deployment.package import package_commit, resolve_commit
from deployment.server import Conflict, canonical

PUBLIC_REPOSITORY = 'https://github.com/metalx1993/loldex.git'



def validate_cache_config(repo):
    repo=Path(repo)
    config = repo/'config'
    try:
        info = config.lstat()
    except OSError as exc:
        raise ValueError('bare Git cache configuration is missing') from exc
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Git cache configuration must be a private regular file')
    parsed=configparser.RawConfigParser(strict=True)
    parsed.read_string(config.read_text())
    required={'repositoryformatversion':'0','filemode':'true','bare':'true'}
    actual = dict(parsed['core']) if parsed.has_section('core') else {}
    optional = {'ignorecase', 'precomposeunicode'}
    if (parsed.defaults() or parsed.sections()!=['core'] or
            any(actual.get(k) != v for k,v in required.items()) or
            set(actual)-set(required)-optional or
            any(actual[k] not in ('true','false') for k in optional & set(actual))):
        raise ValueError('Git cache requires pristine bare configuration, no hooks/includes/URL rewrites')
    if (repo/'objects/info/alternates').exists() or (repo/'objects/info/alternates').is_symlink():
        raise ValueError('Git cache cannot use alternate object stores')

def network_git(repo, *args):
    validate_cache_config(repo)
    env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.pop('SSH_ASKPASS', None)
    env.update(GIT_TERMINAL_PROMPT='0', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               PATH='/usr/bin:/bin:/usr/local/bin')
    command=['/usr/bin/git','-C',str(repo),'-c','credential.helper=','-c','core.hooksPath=/dev/null',
             '-c','protocol.allow=never','-c','protocol.https.allow=always',
             '-c','http.sslVerify=true','-c','http.followRedirects=false',
             '-c','gc.auto=0','-c','maintenance.auto=false',*args]
    return subprocess.run(command,env=env,capture_output=True,check=True,timeout=180).stdout


def publish_latest(repo, store):
    repo=Path(repo)
    if not repo.is_dir() or repo.is_symlink() or repo != repo.resolve():
        raise ValueError('supply an existing canonical private bare Git repository')
    if (repo == store.public or store.public in repo.parents or repo in store.public.parents
            or repo == store.control or repo in store.control.parents):
        raise ValueError('Git cache cannot overlap public or contain control authority')
    for part in (repo, *repo.parents):
        if part.is_symlink():
            raise ValueError('Git cache ancestors cannot be symlinks')
    validate_cache_config(repo)
    expected=store.status()  # capture before fetch, never refresh silently on CAS conflict
    network_git(repo,'fetch','--depth=1','--no-tags','--no-recurse-submodules',PUBLIC_REPOSITORY,'refs/heads/main')
    commit=resolve_commit(repo,'FETCH_HEAD')
    raw=package_commit(repo,commit)
    # Package includes verified Git object bytes and generated dataset hashes.
    # Upstream health was validated by the GitHub publication workflow at this commit.
    remote=network_git(repo,'ls-remote',PUBLIC_REPOSITORY,'refs/heads/main').decode().split()
    if len(remote)!=2 or not re.fullmatch('[0-9a-f]{40}',remote[0]) or remote[0]!=commit or remote[1]!='refs/heads/main':
        raise Conflict('main moved during packaging; discard and run a fresh cycle')
    rid=store.install(raw)
    token=store.activate(rid,expected)
    return {'release_id':rid,'commit':commit,'active':token,'scheduler_enabled':False}


def main(argv=None):
    import argparse
    from deployment.server import ReleaseStore
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--public-root',type=Path,required=True)
    p.add_argument('--control-root',type=Path,required=True)
    a=p.parse_args(argv)
    print(canonical(publish_latest(a.repo,ReleaseStore(a.public_root,a.control_root))).decode())

if __name__=='__main__':main()
