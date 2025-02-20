# This file is part of Indico.
# Copyright (C) 2002 - 2024 CERN
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see the
# LICENSE file for more details.

import textwrap
from enum import Enum
from itertools import count

import pytest

from indico.util.string import (AutoLinkExtension, HTMLLinker, camelize, camelize_keys, crc32, format_email_with_name,
                                format_repr, html_to_plaintext, make_unique_token, normalize_phone_number,
                                render_markdown, sanitize_email, sanitize_for_platypus, sanitize_html, seems_html,
                                slugify, snakify, snakify_keys, strip_tags, text_to_repr)


def test_seems_html():
    assert seems_html('<b>test')
    assert seems_html('a <b> c')
    assert not seems_html('test')
    assert not seems_html('a < b > c')


def test_make_unique_token(monkeypatch):
    monkeypatch.setattr('indico.util.string.uuid4', lambda _counter=count(): str(next(_counter)))  # noqa: B008
    tokens = {'1', '3'}

    def _get_token():
        token = make_unique_token(lambda t: t not in tokens)
        tokens.add(token)
        return token

    assert _get_token() == '0'
    assert _get_token() == '2'
    assert _get_token() == '4'
    assert _get_token() == '5'


@pytest.mark.parametrize(('input', 'output'), (
    ('this is a    test',    'this-is-a-test'),
    ('this is \xe4    test', 'this-is-ae-test'),
    ('12345!xxx   ',         '12345xxx'),
))
def test_slugify(input, output):
    assert slugify(input) == output


def test_slugify_maxlen():
    assert slugify('foo bar', maxlen=5) == 'foo-b'


def test_slugify_args():
    assert slugify('foo', 123, 'bar') == 'foo-123-bar'
    assert slugify('m\xf6p', 123, 'b\xe4r') == 'moep-123-baer'


@pytest.mark.parametrize(('input', 'lower', 'output'), (
    ('Test', True, 'test'),
    ('Test', False, 'Test'),
    ('m\xd6p', False, 'mOep'),
    ('m\xd6p', True, 'moep')
))
def test_slugify_lower(input, lower, output):
    assert slugify(input, lower=lower) == output


def test_strip_tags():
    assert strip_tags('foo <strong>bar</strong>') == 'foo bar'


@pytest.mark.parametrize(('input', 'html', 'max_length', 'output'), (
    ('Hello\n  \tWorld',  False, None, 'Hello World'),
    ('Hello<b>World</b>', False, None, 'Hello<b>World</b>'),
    ('Hello<b>World</b>', True,  None, 'HelloWorld'),
    ('Hi <b>a</b> <br>',  True,  None, 'Hi a'),
    ('x' * 60,            False, None, 'x' * 60),
    ('x' * 60,            False, 50,   'x' * 50 + '...'),
    ('x' * 50,            False, 50,   'x' * 50)
))
def test_text_to_repr(input, html, max_length, output):
    assert text_to_repr(input, html=html, max_length=max_length) == output


@pytest.mark.parametrize(('args', 'kwargs', 'output'), (
    ((), {}, '<Foo()>'),
    (('id', 'hello', 'dct'), {}, "<Foo(1, world, {'a': 'b'})>"),
    (('id',), {}, '<Foo(1)>'),
    (('id', 'enum'), {}, '<Foo(1, foo)>'),
    (('id',), {'flag1': True, 'flag0': False}, '<Foo(1)>'),
    (('id',), {'flag1': False, 'flag0': False}, '<Foo(1, flag1=True)>'),
    (('id',), {'flag1': False, 'flag0': True}, '<Foo(1, flag0=False, flag1=True)>'),
    (('id',), {'flag1': False, 'flag0': True, '_text': 'moo'}, '<Foo(1, flag0=False, flag1=True): "moo">')

))
def test_format_repr(args, kwargs, output):
    class Foo:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class MyEnum(Enum):
        foo = 'bar'

    obj = Foo(id=1, enum=MyEnum.foo, hello='world', dct={'a': 'b'}, flag1=True, flag0=False)
    assert format_repr(obj, *args, **kwargs) == output


@pytest.mark.parametrize(('input', 'output'), (
    ('',       ''),
    ('FooBar', 'foo_bar'),
    ('fooBar', 'foo_bar'),
    ('fooBAR', 'foo_bar'),
    ('bar',    'bar'),
    ('Bar',    'bar'),
    ('aaBbCc', 'aa_bb_cc'),
))
def test_snakify(input, output):
    assert snakify(input) == output


@pytest.mark.parametrize(('input', 'output'), (
    ('_',        '_'),
    ('_foo_bar', '_fooBar'),
    ('foo',      'foo'),
    ('fooBar',   'fooBar'),
    ('foo_bar',  'fooBar'),
    ('aa_bb_cC', 'aaBbCc'),
))
def test_camelize(input, output):
    assert camelize(input) == output


def test_camelize_keys():
    d = {'fooBar': 'foo', 'bar_foo': 123, 'moo_bar': {'hello_world': 'test'},
         'nested': [{'is_dict': True}, 'foo', ({'a_b': 'c'},)]}
    orig = d.copy()
    d2 = camelize_keys(d)
    assert d == orig  # original dict not modified
    assert d2 == {'fooBar': 'foo', 'barFoo': 123, 'mooBar': {'helloWorld': 'test'},
                  'nested': [{'isDict': True}, 'foo', ({'aB': 'c'},)]}

    # Keys starting with an underscore should not change
    d = camelize_keys({'_deleted': True})
    assert d == {'_deleted': True}

    # 'url' is always camelized as 'URL' instead of 'Url'
    d = {'avatar_url': 'avatar/1', 'upload_url_materials': '/upload/materials',
         'url_download': '/download', 'saveURL': '/save'}
    orig = d.copy()
    d2 = camelize_keys(d)
    assert d == orig  # original dict not modified
    assert d2 == {'avatarURL': 'avatar/1', 'uploadURLMaterials': '/upload/materials',
                  'urlDownload': '/download', 'saveURL': '/save'}


def test_snakify_keys():
    d = {'sn_case': 2, 'shouldBeSnakeCase': 3, 'snake': 4, 'snake-case': 5, 'inner': {'innerDict': 2}}
    orig = d.copy()
    d2 = snakify_keys(d)
    assert d == orig
    assert d2 == {'sn_case': 2, 'should_be_snake_case': 3, 'snake': 4, 'snake-case': 5, 'inner': {'inner_dict': 2}}


def test_crc32():
    assert crc32('m\xf6p') == 2575016153
    assert crc32('m\xf6p'.encode()) == 2575016153
    assert crc32(b'') == 0
    assert crc32(b'hello world\0\1\2\3\4') == 140159631


@pytest.mark.parametrize(('input', 'output'), (
    ('',                ''),
    ('+41785324567',    '+41785324567'),
    ('++454545455',     '+454545455'),
    ('123-456-789',     '123456789'),
    ('0123456x0+',      '0123456x0'),
    ('+48 785 326 691', '+48785326691'),
    ('0048785326691',   '0048785326691'),
    ('123-456-xxxx',    '123456xxxx')
))
def test_normalize_phone_number(input, output):
    assert normalize_phone_number(input) == output


@pytest.mark.parametrize(('input', 'output'), (
    ('', ''),
    ('foo', 'foo'),
    ('foo@bar.fb', 'foo@bar.fb'),
    ('<foo@bar.fb>', 'foo@bar.fb'),
    ('foobar <foo@bar.fb> asdf', 'foo@bar.fb'),
    ('foobar <foo@bar.fb> <test@test.com>', 'foo@bar.fb')
))
def test_sanitize_email(input, output):
    assert sanitize_email(input) == output


@pytest.mark.parametrize(('input', 'output'), (
    ('Simple text', 'Simple text'),
    ('<span>Simple text</span>', 'Simple text'),
    ('<p>Simple text</p>', 'Simple text'),
    ('<h1>Some html</h1>', 'Some html'),
    ('foo &amp; bar <a href="test">xxx</a> 1<2 <test>', 'foo & bar xxx 1<2'),
    ('<strong>m\xf6p</strong> test', 'm\xf6p test'),
    ('<p>hello</p> <p>world</p>', 'hello\n world'),
    ('Text <br> with <br> linebreaks', 'Text \n with \n linebreaks'),
    ('<p>Combining paragraphs with <br> linebreaks </p>', 'Combining paragraphs with \n linebreaks'),
))
def test_html_to_plaintext(input, output):
    assert html_to_plaintext(input) == output


@pytest.mark.parametrize(('input', 'output'), (
    ('*coconut*', '<p><em>coconut</em></p>'),
    ('**swallow**', '<p><strong>swallow</strong></p>'),
    ('<span>Blabla **strong text**</span>', '<p>&lt;span&gt;Blabla <strong>strong text</strong>&lt;/span&gt;</p>'),
    ('[Python](http://www.google.com/search?q=holy+grail&ln=fr)',
     '<p><a href="http://www.google.com/search?q=holy+grail&amp;ln=fr">Python</a></p>'),
    ("<script>alert('I'm evil!')</script>", "&lt;script&gt;alert('I'm evil!')&lt;/script&gt;"),
    ('Name|Colour\n---|---\nLancelot|Blue',
     '<table>\n<thead>\n<tr>\n<th>Name</th>\n<th>Colour</th>\n</tr>\n</thead>\n<tbody>\n<tr>\n<td>Lancelot</td>\n'
     '<td>Blue</td>\n</tr>\n</tbody>\n</table>'),
    ('**$2 * 2 * 2 > 7$**', '<p><strong>$2 * 2 * 2 > 7$</strong></p>'),
    ('Escaping works just fine! $ *a* $', '<p>Escaping works just fine! $ *a* $</p>'),
    ('![Just a cat](http://myserver.example.com/cat.png)', '<p><img alt="Just a cat" '
     'src="http://myserver.example.com/cat.png"></p>'),
    ('<https://getindico.io>', '<p><a href="https://getindico.io">https://getindico.io</a></p>')
))
def test_markdown(input, output):
    assert render_markdown(input, extensions=('tables',)) == output


def test_markdown_sanitize_css():
    input = '<img src="foo.png" style="wtf: isthis; text-align: center;"> **test**'
    output = '<p><img src="foo.png" style="text-align: center;"> <strong>test</strong></p>'
    assert render_markdown(input) == output


def test_sanitize_html_imagemaps():
    html = '''
        <img src="example.jpg" usemap="#image-map">
        <map name="image-map">
            <area alt="test" coords="1,2,3,4" href="//example.com" shape="rect" target="_blank" title="test">
        </map>
    '''
    assert sanitize_html(html) == html


def test_sanitize_for_platypus_relative_urls():
    html = textwrap.dedent('''
        <p>
            <img src="https://example.com/test.png"/>
            <img src="//example.com/test.png"/>
            <img src="/test.png"/>
        </p>
    ''').strip()
    expected = textwrap.dedent('''
        <p>
            <img src="https://example.com/test.png"/>
            <img src="http://example.com/test.png"/>
            <img src="http://localhost/test.png"/>
        </p>
    ''').strip()
    assert sanitize_for_platypus(html) == expected


@pytest.mark.parametrize(('input', 'output'), (
    ('<span style=\'font-family:"Liberation Serif",serif;\'>test</span>',
     '<span style=\'font-family:"Liberation Serif",serif;\'>test</span>'),
    ('<span style="font-family:&quot;Liberation Serif&quot;,serif">test</span>',
     '<span style=\'font-family:"Liberation Serif",serif;\'>test</span>'),
    ('<span style="font-family:&quot;Liberation Serif&quot;,serif;font-size:14px">test</span>',
     '<span style=\'font-family:"Liberation Serif",serif;font-size:14px;\'>test</span>'),
    ('<span>test &quot;</span>', '<span>test &quot;</span>'),  # Only convert escaped quotes inside style attributes
))
def test_sanitize_html_escaped_quotes(input, output):
    assert sanitize_html(input) == output


@pytest.mark.parametrize(('name', 'address', 'expected'), (
    ('GuineaPig', 'test@example.com', 'GuineaPig <test@example.com>'),
    ('Guinea Pig', 'test@example.com', 'Guinea Pig <test@example.com>'),
    ('Guinea,Pig', 'test@example.com', '"Guinea,Pig" <test@example.com>'),
    ('John "Guinea Pig" Doe', 'test@example.com', '"John \\"Guinea Pig\\" Doe" <test@example.com>'),
))
def test_format_email_with_name(name, address, expected):
    assert format_email_with_name(name, address) == expected


LINKER_RULES = [
    {'regex': r'#(\d+)', 'url': 'https://gitclub.in/ticket/{1}'}
]


@pytest.mark.parametrize(('input', 'output'), (
    ('<a href="https://cern.ch">#1234</a>', '<a href="https://cern.ch">#1234</a>'),
    ('<p><a href="https://cern.ch">#1234</a> and #1234</p>',
     '<p><a href="https://cern.ch">#1234</a> and <a href="https://gitclub.in/ticket/1234">#1234</a></p>'),
    ('#1234 and #123455',
     '<a href="https://gitclub.in/ticket/1234">#1234</a> and <a href="https://gitclub.in/ticket/123455">#123455</a>')
))
def test_html_linker(input, output):
    linker = HTMLLinker(LINKER_RULES)
    assert linker.process(input) == output


@pytest.mark.parametrize(('input', 'output'), (
    ('This is #12345', '<p>This is <a href="https://gitclub.in/ticket/12345">#12345</a></p>'),
    ('This is [#12345](https://getindico.io)', '<p>This is <a href="https://getindico.io">#12345</a></p>'),
    ('Tickets #12345#1235',
     '<p>Tickets <a href="https://gitclub.in/ticket/12345">#12345</a>'
     '<a href="https://gitclub.in/ticket/1235">#1235</a></p>'),
    ('#12345', '<h1>12345</h1>')
))
def test_markdown_linker(input, output):
    assert render_markdown(input, extensions=('nl2br', AutoLinkExtension(LINKER_RULES))) == output
