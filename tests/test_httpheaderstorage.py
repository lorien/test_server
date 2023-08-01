import pytest

from test_server.structure import HttpHeaderStorage


def test_constructor_no_data() -> None:
    HttpHeaderStorage()


def test_constructor_dict() -> None:
    HttpHeaderStorage({"foo": "bar"})


def test_constructor_list() -> None:
    HttpHeaderStorage([("foo", "bar")])


def test_set_get_simple_value() -> None:
    obj = HttpHeaderStorage()
    obj.set("foo", "bar")
    assert obj.get("foo") == "bar"


def test_set_get_multi_value() -> None:
    obj = HttpHeaderStorage()
    obj.add("foo", "bar")
    obj.add("foo", "baz")
    assert obj.getlist("foo") == ["bar", "baz"]


def test_delitem() -> None:
    obj = HttpHeaderStorage()
    with pytest.raises(KeyError):
        obj.remove("foo")
    obj.set("foo", "bar")
    obj.remove("foo")
    with pytest.raises(KeyError):
        obj.remove("foo")


def test_repr() -> None:
    obj = HttpHeaderStorage()
    obj.add("foo", "bar")
    obj.add("foo", "baz")
    assert repr(obj) == "[('foo', 'bar'), ('foo', 'baz')]"


def test_constructor_key_multivalue() -> None:
    obj = HttpHeaderStorage([("set-cookie", "foo=bar"), ("set-cookie", "baz=gaz")])
    assert obj.getlist("set-cookie") == ["foo=bar", "baz=gaz"]


def test_count_keys() -> None:
    obj = HttpHeaderStorage()
    obj.add("foo", "bar")
    obj.add("foo", "baz")
    assert obj.count_keys() == 1  # noqa: PLR2004


def test_count_items() -> None:
    obj = HttpHeaderStorage()
    obj.add("foo", "bar")
    obj.add("foo", "baz")
    assert obj.count_items() == 2  # noqa: PLR2004
