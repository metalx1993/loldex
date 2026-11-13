"""Static URL closure lint rejects bypasses of immutable release-prefixed assets."""
from pathlib import Path

import pytest

from deployment.url_closure import validate_url_closure
from deployment.package import build_package


@pytest.mark.parametrize('markup', [
    '<script src="/experience.js"></script>',
    '<link rel="stylesheet" href="/experience.css">',
    '<link rel="icon" href="/favicon.svg">',
    '<img src="/logo.png">',
    '<script>fetch("/data.json")</script>',
    '<script>fetch("https://loldex.sh/catalog.json")</script>',
    '<base href="./">',
    '<base href="https://example.test/">',
    '<a href="/search.html">Index</a>',
    '<a href="https://loldex.sh/search.html">Index</a>',
    '<script src="https://example.test/app.js"></script>',
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Example">',
    '<img srcset="./one.png 1x, /two.png 2x">',
    '<img src="&#47;logo.png">',
    '<meta http-equiv="refresh" content="0;url=/index.html">',
    '<form action="/contact.php"></form>',
    '<button formaction="https://loldex.sh/contact.php">Send</button>',
    '<div style="background:url(/image.png)"></div>',
    '<style>@import "/style.css";</style>',
    '<script>fetch/* comment */("/data.json")</script>',
    '<script>fetch("\\u002fdata.json")</script>',
    '<script>fetch("\\x2fdata.json")</script>',
    '<script>fetch("\\u{2f}data.json")</script>',
    '<script>fetch(`/data.json?id=${id}`)</script>',
    '<img src="%2flogo.png">',
    '<script>fetch("../data.json")</script>',
    '<script>import("/module.js")</script>',
    '<script>image.src = "/logo.png";</script>',
    '<script>location.href = "/index.html";</script>',
    '<script>const attrs = {href: "/search.html"};</script>',
    '<div onclick="fetch(\'/data.json\')"></div>',
])
def test_static_root_or_external_runtime_surfaces_are_rejected(markup):
    with pytest.raises(ValueError):
        validate_url_closure({'index.html': markup.encode()})


@pytest.mark.parametrize('source,content', [
    ('style.css', b'body { background: url(/logo.png) }'),
    ('style.css', b'@font-face { src: url(https://fonts.gstatic.com/font.woff2); }'),
    ('style.css', b'@import url(https://fonts.googleapis.com/css2?family=Example);'),
    ('app.js', b'fetch("/data.json")'),
    ('app.js', b'fetch("https://loldex.sh/data.json")'),
    ('app.js', b'fetch("https://www.loldex.sh/data.json")'),
    ('app.js', b'fetch("//example.test/data.json")'),
])
def test_css_and_javascript_files_are_linted(source, content):
    with pytest.raises(ValueError):
        validate_url_closure({source: content})


def test_relative_assets_and_external_navigation_and_identity_metadata_pass():
    files = {'index.html': b'''<link rel="canonical" href="https://loldex.sh/">
    <meta property="og:image" content="https://loldex.sh/og-image.png">
    <script src="./app.js"></script><link rel="stylesheet" href="./app.css">
    <link rel="icon" href="./favicon.svg"><a href="https://attack.mitre.org/">MITRE</a>
    <a href="mailto:contact@example.test">Contact</a><a href="#main">Skip</a>
    <script>fetch('./' + file); fetch('./data.json');</script>''',
             'app.css': b'body { background: url(./logo.png); }',
             'app.js': b'const url = "http://www.w3.org/2000/svg"; fetch("./data.json")'}
    validate_url_closure(files)


def test_relative_parent_reference_is_allowed_only_when_inside_release():
    validate_url_closure({'nested/page.html': b'<script src="../app.js"></script>'})
    with pytest.raises(ValueError):
        validate_url_closure({'page.html': b'<script src="../app.js"></script>'})
    with pytest.raises(ValueError):
        validate_url_closure({'nested/page.html': b'<script src="../../app.js"></script>'})


def test_metadata_relation_cannot_smuggle_a_runtime_stylesheet():
    with pytest.raises(ValueError):
        validate_url_closure({'index.html': b'<link rel="canonical stylesheet" href="https://loldex.sh/style.css">'})


def test_package_validation_invokes_url_closure():
    with pytest.raises(ValueError, match='root-relative'):
        build_package({'index.html': b'<script src="/app.js"></script>'}, 'a' * 40)


def test_actual_reviewed_site_satisfies_the_static_closure_guard():
    root = Path(__file__).resolve().parents[1] / 'site'
    files = {path.relative_to(root).as_posix(): path.read_bytes()
             for path in root.rglob('*') if path.is_file()}
    validate_url_closure(files)


@pytest.mark.parametrize('stylesheet', [
    br'body{background:url(\2f logo.png)}',
    br'body{background:url("\00002flogo.png")}',
    br'@import "\2f style.css";',
])
def test_css_hex_escapes_cannot_bypass_release_boundary(stylesheet):
    with pytest.raises(ValueError):
        validate_url_closure({'app.css': stylesheet})


@pytest.mark.parametrize('script', [br'fetch("\57catalog.json")', br'fetch("\057catalog.json")'])
def test_legacy_octal_javascript_literal_escapes_are_rejected(script):
    with pytest.raises(ValueError):
        validate_url_closure({'app.js': script})


def test_safe_string_replacement_is_not_mistaken_for_a_network_call():
    validate_url_closure({'app.js': b'const safe = value.replace("/", "-");'})


@pytest.mark.parametrize('markup', [
    b'<svg><image xlink:href="/image.svg"/></svg>',
    b'<svg><use href="https://loldex.sh/icons.svg#logo"/></svg>',
    b'<?xml-stylesheet href="/style.css"?><svg/>',
    b'<!DOCTYPE svg SYSTEM "https://example.test/foreign.dtd"><svg/>',
])
def test_simple_svg_assets_cannot_load_unversioned_resources(markup):
    with pytest.raises(ValueError):
        validate_url_closure({'favicon.svg': markup})


def test_html_preload_imagesrcset_is_not_an_unchecked_runtime_surface():
    with pytest.raises(ValueError):
        validate_url_closure({'index.html': b'<link rel="preload" imagesrcset="/a.png 1x">'})
