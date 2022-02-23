import pytest

from test_server.structure import HttpHeaderStorage


def test_constructor_no_data():
    HttpHeaderStorage()


def test_constructor_dict():
    HttpHeaderStorage({"foo": "bar"})


def test_constructor_list():
    HttpHeaderStorage([("foo", "bar")])


def test_set_get_simple_value():
    obj = HttpHeaderStorage()
    obj.set("foo", "bar")
    assert obj.get("foo") == "bar"


def test_set_get_multi_value():
    obj = HttpHeaderStorage()
    obj.add("foo", "bar")
    obj.add("foo", "baz")
    assert obj.getlist("foo") == ["bar", "baz"]


def test_delitem():
    obj = HttpHeaderStorage()
    with pytest.raises(KeyError):
        obj.remove("foo")
    obj.set("foo", "bar")
    obj.remove("foo")
    with pytest.raises(KeyError):
        obj.remove("foo")


def test_repr():
    obj = HttpHeaderStorage()
    obj.add("foo", "bar")
    obj.add("foo", "baz")
    assert repr(obj) == "[('foo', 'bar'), ('foo', 'baz')]"


def test_constructor_key_multivalue():
    obj = HttpHeaderStorage([("set-cookie", "foo=bar"), ("set-cookie", "baz=gaz")])
    assert obj.getlist("set-cookie") == ["foo=bar", "baz=gaz"]


def test_count_keys():
    obj = HttpHeaderStorage()
    obj.add("foo", "bar")
    obj.add("foo", "baz")
    assert 1 == obj.count_keys()


def test_count_items():
    obj = HttpHeaderStorage()
    obj.add("foo", "bar")
    obj.add("foo", "baz")
    assert 2 == obj.count_items()
