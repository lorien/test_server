import pytest

from test_server.container import CallbackDict


class Reg(CallbackDict):
    writed = 0
    readed = 0

    def write_callback(self):
        self.writed += 1

    def read_callback(self):
        self.readed += 1


def test_init():
    foo = Reg(dict(a=1, b=2))


def test_default_get_set():
    foo = Reg(dict(a=1, b=2))
    assert foo['a'] == 1
    assert foo['b'] == 2
    foo['a'] = 3
    foo['c'] = 4
    assert foo['a'] == 3
    assert foo['c'] == 4


def test_get_callback():
    foo = Reg(dict(a=1))
    a  = foo['a']
    assert a == 1
    assert foo.writed == 0
    assert foo.readed == 1


def test_set_callback():
    foo = Reg(dict(a=1))
    foo['a'] = 2
    assert foo.writed == 1
    assert foo.readed == 0


def test_update_callback():
    foo = Reg(dict(a=1))
    foo.update({'a': 2})
    assert foo.writed == 1
    assert foo.readed == 0


def test_clear_callback():
    foo = Reg(dict(a=1))
    foo['a'] = 2
    foo.clear()
    assert foo.writed == 2
    with pytest.raises(KeyError):
        bar = foo['a']


def test_unimplemented_attrs():
    foo = Reg(dict(a=1))
    with pytest.raises(NotImplementedError):
        foo.get('a')
        foo.set('a', 1)
        foo.update({})
        foo.keys()
