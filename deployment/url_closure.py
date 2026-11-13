"""Release URL lint for LOLDEX's reviewed HTML/CSS/JS stack.

This is deliberately not a proof of arbitrary JavaScript URL construction or a
replacement for the host's browser acceptance test. It rejects static references
that would bypass the immutable release prefix in the current architecture.
"""
from __future__ import annotations

from html.parser import HTMLParser
import posixpath
import re
from urllib.parse import unquote, urlsplit

_SAME_ORIGIN = {'loldex.sh', 'www.loldex.sh'}
_SPACE = r'(?:\s|/\*[\s\S]*?\*/)*'
_LITERAL = r'''(?P<quote>['"`])(?P<value>(?:\\[\s\S]|(?!(?P=quote))[\s\S])*?)(?P=quote)'''
_CALLS = re.compile(r'\b(?:fetch|import|location\.(?:assign|replace))' + _SPACE + r'\(' + _SPACE + _LITERAL)
_ASSIGN = re.compile(r'(?:\.(?:src|href)|\blocation(?:\.href)?|\b(?:src|href)\s*:)' + _SPACE + r'(?:=' + _SPACE + r')?' + _LITERAL)
_CSS_URL = re.compile(r'url\(' + r'\s*(?:([\'"])(.*?)\1|([^)]*))\s*\)', re.I | re.S)
_CSS_IMPORT = re.compile(r'@import\s+([\'"])(.*?)\1', re.I | re.S)


def _decode_js(value):
    output, index = [], 0
    escapes = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0'}
    while index < len(value):
        character = value[index]
        index += 1
        if character != '\\':
            output.append(character)
            continue
        if index >= len(value):
            raise ValueError('unterminated JavaScript URL escape')
        escape = value[index]
        index += 1
        if escape in '1234567':
            raise ValueError('legacy octal JavaScript URL escapes are unsupported')
        if escape in {'x', 'u'}:
            length = 2 if escape == 'x' else 4
            if escape == 'u' and index < len(value) and value[index] == '{':
                end = value.find('}', index)
                digits = value[index + 1:end] if end >= 0 else ''
                index = end + 1
            else:
                digits = value[index:index + length]
                index += length
                if len(digits) != length:
                    raise ValueError('invalid JavaScript URL escape')
            if not digits or not re.fullmatch(r'[0-9a-fA-F]{1,6}', digits):
                raise ValueError('invalid JavaScript URL escape')
            try:
                output.append(chr(int(digits, 16)))
            except ValueError as exc:
                raise ValueError('invalid JavaScript URL escape') from exc
        elif escape == '\n':
            continue
        elif escape == '\r':
            if index < len(value) and value[index] == '\n':
                index += 1
        else:
            output.append(escapes.get(escape, escape))
    return ''.join(output)


def _decode_css(value):
    # CSS escapes are hex with an optional terminator, unlike JavaScript's
    # \x/\u escapes. Decode before checking release boundaries.
    pattern = re.compile(r'\\([0-9a-fA-F]{1,6})(?:\r\n|[ \t\r\n\f])?|\\(\r\n|[\s\S])')

    def replace(match):
        if match.group(1):
            scalar = int(match.group(1), 16)
            if scalar == 0 or scalar > 0x10FFFF or 0xD800 <= scalar <= 0xDFFF:
                raise ValueError('invalid CSS URL escape')
            return chr(scalar)
        escaped = match.group(2)
        return '' if escaped in {'\n', '\r', '\r\n', '\f'} else escaped

    return pattern.sub(replace, value)


def _runtime_url(value, source, *, navigation=False):
    value = value.strip()
    if not value:
        return
    if any(ord(c) < 32 or ord(c) == 127 for c in value) or '\\' in value:
        raise ValueError(f'{source}: runtime URL has controls or backslashes')
    if value.startswith('/'):
        raise ValueError(f'{source}: root-relative runtime URL escapes release')
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme in {'http', 'https'} and parsed.hostname in _SAME_ORIGIN:
            raise ValueError(f'{source}: absolute same-origin URL bypasses release')
        if navigation and parsed.scheme in {'https', 'http', 'mailto', 'tel'} and not parsed.username and not parsed.password:
            return
        raise ValueError(f'{source}: external or unsupported runtime resource URL')
    decoded = unquote(parsed.path)
    if decoded.startswith('/') or '\\' in decoded or any(ord(c) < 32 for c in decoded):
        raise ValueError(f'{source}: encoded runtime URL escapes release')
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), decoded))
    if resolved == '..' or resolved.startswith('../'):
        raise ValueError(f'{source}: relative runtime URL escapes release')


def _javascript(text, source):
    for match in _CALLS.finditer(text):
        _runtime_url(_decode_js(match['value']), source)
    for match in _ASSIGN.finditer(text):
        _runtime_url(_decode_js(match['value']), source)


def _css(text, source):
    for match in _CSS_URL.finditer(text):
        value = (match.group(2) if match.group(1) else match.group(3)).strip()
        _runtime_url(_decode_css(value), source)
    for match in _CSS_IMPORT.finditer(text):
        _runtime_url(_decode_css(match.group(2)), source)


class _HTML(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.capture, self.buffer = None, []

    def handle_starttag(self, tag, attributes):
        attrs = {}
        for name, value in attributes:
            if name in attrs:
                raise ValueError(f'{self.source}: duplicate HTML attribute')
            attrs[name] = value or ''
        if tag == 'base':
            raise ValueError(f'{self.source}: base element can bypass release URL closure')
        if {'srcset', 'imagesrcset'} & attrs.keys() or tag in {'iframe', 'object', 'embed', 'foreignobject'}:
            raise ValueError(f'{self.source}: unsupported embedded URL surface')
        if tag == 'meta' and attrs.get('http-equiv', '').lower() == 'refresh':
            raise ValueError(f'{self.source}: meta refresh bypasses release navigation')
        rel = set(attrs.get('rel', '').lower().split())
        metadata_link = tag == 'link' and bool(rel) and rel <= {'canonical', 'preconnect', 'dns-prefetch'}
        for attribute in ('src', 'href', 'xlink:href', 'poster', 'action', 'formaction'):
            if attribute not in attrs:
                continue
            if attribute == 'href' and metadata_link:
                # Canonical/connection hints describe public identity/providers;
                # they do not load the release's data or executable code.
                continue
            is_navigation = tag in {'a', 'area'} and attribute == 'href'
            _runtime_url(attrs[attribute], self.source, navigation=is_navigation)
        if 'style' in attrs:
            _css(attrs['style'], self.source)
        for attribute, value in attrs.items():
            if attribute.startswith('on'):
                _javascript(value, self.source)
        if tag in {'script', 'style'}:
            script_type = attrs.get('type', '').lower()
            if tag == 'style' or script_type in {'', 'module', 'text/javascript', 'application/javascript'}:
                self.capture, self.buffer = tag, []

    def handle_pi(self, data):
        if data.lower().startswith('xml-stylesheet'):
            raise ValueError(f'{self.source}: external XML stylesheet surface unsupported')

    def handle_decl(self, decl):
        if self.source.lower().endswith('.svg'):
            raise ValueError(f'{self.source}: SVG document declarations are unsupported')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == self.capture:
            text = ''.join(self.buffer)
            (_javascript if tag == 'script' else _css)(text, self.source)
            self.capture, self.buffer = None, []

    def finish(self):
        if self.capture:
            text = ''.join(self.buffer)
            (_javascript if self.capture == 'script' else _css)(text, self.source)


def validate_url_closure(files):
    """Lint static URL surfaces of the reviewed stack; never modify package bytes."""
    for source, raw in files.items():
        suffix = posixpath.splitext(source)[1].lower()
        if suffix not in {'.html', '.htm', '.css', '.js', '.svg'}:
            continue
        try:
            text = raw.decode('utf-8')
        except UnicodeError as exc:
            raise ValueError(f'{source}: runtime text must use UTF-8') from exc
        if suffix in {'.html', '.htm', '.svg'}:
            parser = _HTML(source)
            parser.feed(text)
            parser.close()
            parser.finish()
        elif suffix == '.css':
            _css(text, source)
        else:
            _javascript(text, source)
