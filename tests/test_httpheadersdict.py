import pytest

from test_server.structure import HttpHeadersDict


def test_constructor_no_data():
    HttpHeadersDict()


def test_constructor_dict():
    HttpHeadersDict({"foo": "bar"})


def test_constructor_list():
    HttpHeadersDict([("foo", "bar")])


def test_set_get_simple_value():
    obj = HttpHeadersDict()
    obj["foo"] = "bar"
    assert obj["foo"] == b"bar"


def test_set_get_multi_value():
    obj = HttpHeadersDict()
    obj.add("foo", "bar")
    obj.add("foo", "baz")
    assert obj["foo"] == b"bar, baz"


def test_delitem():
    obj = HttpHeadersDict()
    with pytest.raises(KeyError):
        del obj["foo"]

    obj["foo"] = "bar"
    assert len(obj) == 1

    del obj["foo"]
    assert len(obj) == 0


def test_repr():
    obj = HttpHeadersDict()
    obj.add("foo", "bar")
    obj.add("foo", "baz")
    assert repr(obj) == "{'foo': b'bar, baz'}"
