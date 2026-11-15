"""Delivery contracts for browser restrictions and ephemeral CI credentials."""
import json
from html.parser import HTMLParser
from pathlib import Path
import os
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_all_pages_can_load_under_the_delivered_csp():
    for path in (ROOT / 'site').glob('*.html'):
        page = Page()
        page.feed(path.read_text())
        policies = [a['content'] for t, a in page.tags if t == 'meta' and a.get('http-equiv') == 'Content-Security-Policy']
        assert len(policies) == 1, path
        assert "script-src 'self'" in policies[0] and "object-src 'none'" in policies[0]
        assert "unsafe-inline" not in policies[0]
        for tag, attrs in page.tags:
            assert not any(k.startswith('on') or k == 'style' for k in attrs), path
            assert tag != 'style', path
            if tag == 'script':
                assert attrs.get('src', '').startswith('./'), path
                assert (ROOT / 'site' / attrs['src'][2:]).is_file(), path
        assert next(a for t, a in page.tags if t == 'meta' and a.get('name') == 'referrer')['content'] == 'strict-origin-when-cross-origin'


def test_askpass_keeps_token_out_of_remote_url_and_helper(tmp_path):
    workflow = yaml.load((ROOT / '.github/workflows/sync.yml').read_text(), Loader=yaml.BaseLoader)
    steps = {s['name']: s for s in workflow['jobs']['sync']['steps']}
    script = steps['Publish only onto the unchanged acquisition base']['run']
    assert 'remote set-url' not in script and 'x-access-token:${' not in script
    prefix = script.split('          git fetch')[0] if '          git fetch' in script else script.split('git fetch')[0]
    # Run the actual setup snippet with fake token; no network or real credential.
    fake = 'test-token-not-a-real-secret'
    env = dict(os.environ, RUNNER_TEMP=str(tmp_path), SYNC_TOKEN=fake)
    probe = prefix.replace("trap 'rm -f \"$GIT_ASKPASS\"' EXIT", '')
    subprocess.run(['bash', '-euc', probe], env=env, check=True)
    helper = tmp_path / 'loldex-git-askpass'
    assert fake not in helper.read_text()
    assert subprocess.check_output([str(helper), 'Password for https://github.com'], env=env, text=True).strip() == fake
    assert helper.stat().st_mode & 0o077 == 0


def test_locked_test_runtime_has_integrity_for_every_package():
    lock = json.loads((ROOT / 'tests/php-runtime/package-lock.json').read_text())
    package = json.loads((ROOT / 'tests/php-runtime/package.json').read_text())
    assert package['dependencies'] == lock['packages']['']['dependencies'] == {'@php-wasm/node': '3.1.61'}
    for name, data in lock['packages'].items():
        if name:
            assert data['resolved'].startswith('https://registry.npmjs.org/')
            assert data['integrity'].startswith('sha512-')


def test_bootstrap_intercepts_dynamic_retained_paths_before_static_passthrough():
    import re
    source = (ROOT / 'deployment/siteground/bootstrap.htaccess').read_text()
    assert 'Options -Indexes -MultiViews' in source
    assert 'AcceptPathInfo Off' in source
    rules = [line.strip().split()[1:3] for line in source.splitlines()
             if line.strip().startswith('RewriteRule ')]
    def destination(path):
        for pattern, target in rules:
            if re.search(pattern, path):
                return target
    prefix = 'releases/r-' + 'a' * 64 + '/'
    for path in ['api.php', 'api.php/path-info', 'api-v1.php', 'contact.php',
                 'contact.php/path-info', 'api/v1/search', 'api/stats']:
        assert destination(prefix + path) == 'loldex-retained.php', path
    for path in ['data.json', 'index.html', 'evidence-records/abc.json']:
        assert destination(prefix + path) == '-'
    assert destination('loldex-retained.php') == '-'
    assert destination('loldex-router.php') == '-'
    assert destination('.well-known/acme-challenge/token') == '-'
