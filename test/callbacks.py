# Copyright 2015-2017 Gregory Petukhov (lorien@lorien.name)
# *
# Licensed under the MIT License
from six.moves.urllib.error import HTTPError
from six.moves.urllib.request import urlopen

# pylint: disable=redefined-outer-name
import pytest

from .util import (
    global_server, # pylint: disable=unused-import
    server
)


def test_callback(server):
    def get_callback():
        return {
            'type': 'response',
            'body': b'Hello',
            'headers': [
                ('method', 'get'),
            ],
        }

    def post_callback():
        return {
            'type': 'response',
            'body': b'World',
            'headers': [
                ('method', 'post'),
            ],
        }

    server.response['callback'] = get_callback
    info = urlopen(server.get_url())
    assert info.headers['method'] == 'get'
    assert info.read() == b'Hello'

    server.response['post.callback'] = post_callback
    info = urlopen(server.get_url(), b'key=val')
    assert info.headers['method'] == 'post'
    assert info.read() == b'World'


def test_callback_yield_(server):

    def callback():
        return {
            'type': 'response',
            'body': b'HelloWorld',
            'headers': [
                ('method', 'get'),
            ],
        }

    server.response['callback'] = callback
    info = urlopen(server.get_url())
    assert info.headers['method'] == 'get'
    assert info.read() == b'HelloWorld'
