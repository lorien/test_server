import pytest

from test_server.container import CallbackDict


# pylint: disable=abstract-method
class State(CallbackDict):
    writed = 0
    readed = 0

    def write_callback(self):
        self.writed += 1

    def read_callback(self):
        self.readed += 1
# pylint: enable=abstract-method


def test_init():
    State(dict(a=1, b=2))


def test_default_get_set():
    state = State(dict(a=1, b=2))
    assert state['a'] == 1
    assert state['b'] == 2
    state['a'] = 3
    state['c'] = 4
    assert state['a'] == 3
    assert state['c'] == 4


def test_get_callback():
    state = State(dict(a=1))
    assert state['a'] == 1
    assert state.writed == 0
    assert state.readed == 1


def test_set_callback():
    state = State(dict(a=1))
    state['a'] = 2
    assert state.writed == 1
    assert state.readed == 0


def test_update_callback():
    state = State(dict(a=1))
    state.update({'a': 2})
    assert state.writed == 1
    assert state.readed == 0


def test_clear_callback():
    state = State(dict(a=1))
    state['a'] = 2
    state.clear()
    assert state.writed == 2
    with pytest.raises(KeyError):
        state['a'] # pylint: disable=pointless-statement


def test_unimplemented_attrs():
    state = State(dict(a=1))
    with pytest.raises(NotImplementedError):
        state.get('a')
        state.set('a', 1)
        state.update({})
        state.keys()
