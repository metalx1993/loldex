"""Real Apache per-directory routing regressions, with inert text PHP markers.

No PHP handler, installation, public network or production contact request is
used. An OS Apache is optional on developer machines; listener permission must
be granted when the local execution policy blocks loopback sockets.
"""
from contextlib import contextmanager
import grp
import http.client
import os
from pathlib import Path
import pwd
import shutil
import socket
import subprocess
import tempfile
import time

import pytest

ROOT = Path(__file__).resolve().parent.parent
RID = 'r-' + 'a' * 64
RETAINED = '/releases/' + RID
OLD_RULES = r'''
Options -Indexes -MultiViews
DirectoryIndex index.html
RewriteEngine On
RewriteRule ^api/v1/?$ api-v1.php?resource=root [QSA,L]
RewriteRule ^api/v1/(root|entries|entry|search|graph|techniques|technique|identities|identity|evidence|resolve)/?$ api-v1.php?resource=$1 [QSA,L]
RewriteRule ^api/v1/ api-v1.php?resource=unknown [QSA,L]
RewriteRule ^api/([a-z]+)/?$ api.php?action=$1 [QSA,L]
'''


def _apache():
    candidates = [shutil.which('httpd'), shutil.which('apache2'), '/usr/sbin/httpd', '/usr/sbin/apache2']
    binary = next((Path(path) for path in candidates if path and Path(path).is_file()), None)
    modules = next((path for path in [Path('/usr/libexec/apache2'), Path('/usr/lib/apache2/modules')]
                    if (path / 'mod_rewrite.so').is_file()), None)
    if binary is None or modules is None:
        pytest.skip('OS Apache/mod_rewrite unavailable: real retained-release routing gate was not run')
    return binary, modules


@contextmanager
def apache(bootstrap, *, merge_slashes='On'):
    binary, modules = _apache()
    try:
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
    except PermissionError as error:
        pytest.fail('Local Apache gate requires loopback-listener permission: ' + str(error))
    with tempfile.TemporaryDirectory(prefix='loldex-apache-security-', dir='/tmp') as temporary:
        base = Path(temporary)
        base.chmod(0o755)
        public = base / 'public'
        release = public / 'releases' / RID
        release.mkdir(parents=True)
        (public / '.htaccess').write_text(bootstrap)
        (release / '.htaccess').write_text(OLD_RULES)
        (public / 'loldex-router.php').write_text('ROUTER_MARKER')
        (public / 'loldex-retained.php').write_text('BRIDGE_MARKER')
        (release / 'api.php').write_text('OLD_LEGACY_MARKER')
        (release / 'api-v1.php').write_text('OLD_V1_MARKER')
        (release / 'contact.php').write_text('OLD_CONTACT_MARKER')
        (release / 'index.html').write_text('RETAINED_INDEX_MARKER')
        (release / 'data.json').write_text('{"retained":"immutable"}')
        (release / 'style.css').write_text('/* RETAINED_STYLE_MARKER */')
        challenge = public / '.well-known' / 'acme-challenge'
        challenge.mkdir(parents=True)
        (challenge / 'token').write_text('ACME_MARKER')
        (base / 'mime.types').write_text('text/plain php txt\napplication/json json\ntext/html html\ntext/css css\n')
        compiled = subprocess.run([str(binary), '-l'], capture_output=True, text=True, check=True).stdout
        loads = []
        for name, symbol in [('mpm_prefork', 'mpm_prefork'), ('unixd', 'unixd'),
                             ('authz_core', 'authz_core'), ('mime', 'mime'),
                             ('dir', 'dir'), ('rewrite', 'rewrite')]:
            if 'mod_' + name + '.c' in compiled:
                continue
            module = modules / ('mod_' + name + '.so')
            if not module.is_file():
                pytest.skip('OS Apache required module missing: ' + str(module))
            loads.append(f'LoadModule {symbol}_module "{module}"')
        if os.getuid() == 0:
            account = pwd.getpwnam('nobody')
            group = grp.getgrgid(account.pw_gid)
        else:
            account = pwd.getpwuid(os.getuid())
            group = grp.getgrgid(os.getgid())
        configuration = base / 'httpd.conf'
        configuration.write_text('\n'.join([
            f'ServerRoot "{base}"', *loads, f'Listen 127.0.0.1:{port}',
            'ServerName localhost', f'PidFile "{base / "httpd.pid"}"',
            f'ErrorLog "{base / "error.log"}"', 'LogLevel warn',
            f'User {account.pw_name}', f'Group {group.gr_name}',
            f'TypesConfig "{base / "mime.types"}"', f'DocumentRoot "{public}"',
            f'<Directory "{public}">', 'Options FollowSymLinks', 'AllowOverride All',
            'Require all granted', '</Directory>',
            f'MergeSlashes {merge_slashes}', 'AllowEncodedSlashes On',
            'StartServers 1', 'MinSpareServers 1', 'MaxSpareServers 1',
            'ServerLimit 1', 'MaxRequestWorkers 1', 'MaxConnectionsPerChild 100',
        ]) + '\n')
        process = subprocess.Popen([str(binary), '-f', str(configuration), '-DFOREGROUND'],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, start_new_session=True)

        def request(target):
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
            try:
                connection.request('GET', target)
                response = connection.getresponse()
                return response.status, response.read().decode('utf-8', 'replace')
            finally:
                connection.close()

        try:
            started = False
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    output = process.communicate(timeout=1)[0]
                    error_log = (base / 'error.log')
                    pytest.fail('Apache failed to start: ' + output +
                                (error_log.read_text() if error_log.exists() else ''))
                try:
                    request('/.well-known/acme-challenge/token')
                    started = True
                    break
                except OSError:
                    time.sleep(0.05)
            assert started, 'Apache loopback listener did not start'
            yield request
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            process.communicate(timeout=1)


@pytest.mark.parametrize('merge_slashes', ['On', 'Off'])
def test_real_apache_retained_bridge_inherits_before_old_release_rules(merge_slashes):
    bootstrap = (ROOT / 'deployment/siteground/bootstrap.htaccess').read_text()
    with apache(bootstrap, merge_slashes=merge_slashes) as request:
        for endpoint in ['api.php?action=stats', 'api.php?q=one&q=two',
                         'api-v1.php?resource=entries', 'contact.php', 'api/search?q=tar',
                         'api/v1', 'api/v1/entries', 'api/v1/unknown', 'api.php/extra']:
            status, body = request(RETAINED + '/' + endpoint)
            assert (status, body) == (200, 'BRIDGE_MARKER'), (endpoint, status, body[:500])
        for target in [
            '/releases//' + RID + '/api.php', RETAINED + '//api.php',
            RETAINED + '/%61pi.php', RETAINED + '/api%2ephp',
            RETAINED + '/%63ontact.php', RETAINED + '/api%2dv1.php',
            RETAINED + '%2fapi.php', RETAINED + '/api%2fsearch',
        ]:
            status, body = request(target)
            assert (status == 200 and body == 'BRIDGE_MARKER') or status in (400, 404), (target, status, body[:500])
            assert 'OLD_' not in body
        for target, marker in [
            (RETAINED + '/index.html', 'RETAINED_INDEX_MARKER'),
            (RETAINED + '/data.json', '{"retained":"immutable"}'),
            (RETAINED + '/style.css', '/* RETAINED_STYLE_MARKER */'),
            ('/.well-known/acme-challenge/token', 'ACME_MARKER'),
            ('/', 'ROUTER_MARKER'), ('/api/v1/entries', 'ROUTER_MARKER'),
            ('/api/search', 'ROUTER_MARKER'), ('/loldex-router.php', 'ROUTER_MARKER'),
            ('/loldex-retained.php', 'BRIDGE_MARKER'),
        ]:
            status, body = request(target)
            assert (status, body) == (200, marker), (target, status, body[:500])
        assert request(RETAINED + '/missing.json')[0] == 404


def test_real_apache_control_reproduces_child_override_without_inheritance():
    vulnerable = r'''
Options -Indexes -MultiViews
RewriteEngine On
RewriteRule ^loldex-(router|retained)\.php$ - [L]
RewriteRule ^releases/r-[a-f0-9]{64}/(?:api\.php|api-v1\.php|contact\.php|api(?:/.*)?)$ loldex-retained.php [L]
RewriteRule ^releases/ - [L]
RewriteRule ^ loldex-router.php [L]
'''
    with apache(vulnerable) as request:
        assert request(RETAINED + '/api.php?q=one&q=two') == (200, 'OLD_LEGACY_MARKER')
        assert request(RETAINED + '/api/search?q=tar') == (200, 'OLD_LEGACY_MARKER')
