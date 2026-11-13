"""Build a complete five-source publication candidate in a separate checkout.

Explicit D2 snapshot policy: current search contains only this complete verified
snapshot; retired files remain in Git history and prior retained host releases.
The command never fetches, commits, pushes, deploys or enables a schedule.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

from deployment.source_health import prepare_verified_sync
from phase5.vocabulary import SOURCE_UNIVERSE
from scripts.build_all import main as build_all


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()



def guard_targets(repo):
    for target in (repo/'data', repo/'data/entries', repo/'site'):
        if target.is_symlink() or not target.is_dir():
            raise ValueError('candidate output trees must be real directories')
        if any(path.is_symlink() for path in target.rglob('*')):
            raise ValueError('candidate output trees cannot contain symlinks')
    for args in (('ls-files','--others','--exclude-standard','--','data/entries','site','data/source-health.json','data/publication-ledger.json'),
                 ('ls-files','--others','--ignored','--exclude-standard','--','data/entries','site','data/source-health.json','data/publication-ledger.json')):
        if git(repo,*args):
            raise ValueError('untracked or ignored candidate files would be overwritten')

def refresh(repositories, repo, output, expected_base):
    supplied_repo = Path(repo).absolute()
    repo, output = supplied_repo.resolve(), Path(output).resolve()
    if supplied_repo != repo or Path(git(repo, 'rev-parse', '--show-toplevel')) != repo:
        raise ValueError('repo must be the canonical checkout root')
    guard_targets(repo)
    if git(repo, 'rev-parse', 'HEAD') != expected_base:
        raise ValueError('acquisition base differs; do not rebase this candidate')
    if git(repo, 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('candidate checkout must start clean')
    if output == repo or repo in output.parents or output in repo.parents:
        raise ValueError('candidate staging must be outside checkout')
    candidate = prepare_verified_sync(repositories, output, profile='publication-v2')
    # Build every public view before changing the candidate checkout.
    build_all(['--entries', str(candidate/'data/entries'), '--out', str(candidate/'site'),
               '--registry', str(repo/'data/registry/enterprise-attack.json')])
    if git(repo, 'rev-parse', 'HEAD') != expected_base or git(repo, 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('checkout changed while preparing candidate')
    guard_targets(repo)
    def hashes(root):
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(root.rglob('*.yaml'))}
    old = hashes(repo/'data/entries'); new = hashes(candidate/'data/entries')
    ledger = {'version': 1, 'policy': 'D2-five-source-complete-snapshot', 'base_commit': expected_base,
              'publication_profile': 'publication-v2',
              'removed': {p:h for p,h in old.items() if p not in new},
              'added': {p:h for p,h in new.items() if p not in old},
              'updated': {p:{'before':old[p],'after':new[p]} for p in old.keys() & new.keys() if old[p]!=new[p]},
              'retention': 'prior Git commit and immutable host releases; no automatic host garbage collection'}
    # Only a dedicated clean candidate checkout may be mutated by this command.
    shutil.rmtree(repo/'data/entries')
    shutil.copytree(candidate/'data/entries',repo/'data/entries')
    for path in (candidate/'site').iterdir():
        shutil.copyfile(path,repo/'site'/path.name)
    (repo/'data/publication-ledger.json').write_text(json.dumps(ledger,sort_keys=True,separators=(',',':'))+'\n')
    shutil.copyfile(candidate/'source-health.json',repo/'data/source-health.json')
    return ledger


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--expected-base',required=True)
    p.add_argument('--source',action='append',required=True)
    a=p.parse_args(argv);sources={}
    for item in a.source:
        name,sep,path=item.partition('=')
        if not sep or name not in SOURCE_UNIVERSE or name in sources:p.error('unique SOURCE=PATH required')
        sources[name]=(Path(path),'HEAD')
    ledger=refresh(sources,a.repo,a.output,a.expected_base)
    print(json.dumps({'removed':len(ledger['removed']),'added':len(ledger['added']),'updated':len(ledger['updated'])}))
    return 0

if __name__=='__main__':raise SystemExit(main())
