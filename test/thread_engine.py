# Copyright 2015-2017 Gregory Petukhov (lorien@lorien.name)
# *
# Licensed under the MIT License
"""
This module tests features available only
in thread engine: generators, callbacks.
These things could not be used in subprocess engine
because it is not possible to save them in state-share files.
"""
from six.moves.urllib.error import HTTPError
from six.moves.urllib.request import urlopen

# pylint: disable=redefined-outer-name
import pytest

from .server import (global_server, # pylint: disable=unused-import
                     server, skip_by_engine)


@pytest.mark.skip_engine('subprocess')
def test_data_generator(server):
    def gen():
        yield b'one'
        yield b'two'

    server.response['get.data'] = gen()
    assert urlopen(server.get_url()).read() == b'one'
    assert urlopen(server.get_url()).read() == b'two'
    with pytest.raises(HTTPError):
        urlopen(server.get_url())


@pytest.mark.skip_engine('subprocess')
def test_callback(server):
    def get_callback(self):
        self.set_header('method', 'get')
        self.write(b'Hello')
        self.finish()

    def post_callback(self):
        self.set_header('method', 'post')
        self.write(b'Hello')
        self.finish()

    server.response['callback'] = get_callback
    info = urlopen(server.get_url())
    assert info.headers['method'] == 'get'
    assert info.read() == b'Hello'

    server.response['post.callback'] = post_callback
    info = urlopen(server.get_url(), b'key=val')
    assert info.headers['method'] == 'post'
    assert info.read() == b'Hello'


@pytest.mark.skip_engine('subprocess')
def test_callback_yield_(server):

    def callback(self):
        self.set_header('method', 'get')
        self.write(b'Hello')
        yield {'type': 'sleep', 'time': 0.0001}
        self.write(b'World')

        self.finish()

    server.response['callback'] = callback
    info = urlopen(server.get_url())
    assert info.read() == b'HelloWorld'
