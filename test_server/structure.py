# from __future__ import annotations

import typing
from collections import OrderedDict
from pprint import pprint  # pylint: disable=unused-import
from typing import Any, Tuple, Union, cast

# pylint: disable=import-error
from six.moves.collections_abc import Iterator, MutableMapping

# pylint: enable=import-error

__all__ = ["HttpHeaderStorage"]


# pylint: disable=deprecated-typing-alias,consider-alternative-union-syntax,invalid-name
HttpHeaderStream = Union[
    typing.Mapping[str, str],
    typing.Iterable[Tuple[str, str]],
]
# pylint: enable=deprecated-typing-alias,consider-alternative-union-syntax,invalid-name


class HttpHeaderStorage(object):
    """Storage for HTTP Headers.

    The storage maps string keys to one or multiple string values.
    Keys are case insensitive though the original case is stored.
    """

    def __init__(
        self,
        data=None,  # type: None | HttpHeaderStream
        charset="utf-8",  # type: str
    ):
        # type: (...) -> None
        self._store = OrderedDict()  # type: MutableMapping[str, list[str]]
        self._charset = charset
        if data is not None:
            self.extend(data)

    # Public Interface

    def set(self, key, value):
        # type: (str, str) -> None
        # Store original case of key
        self._store[key.lower()] = [key, value]

    def get(self, key):
        # type: (str) -> str
        return self._store[key.lower()][1]

    def getlist(self, key):
        # type: (str) -> list[str]
        return self._store[key.lower()][1:]

    def remove(self, key):
        # type: (str) -> None
        del self._store[key.lower()]

    def add(self, key, value):
        # type: (str, str) -> None
        box = self._store.setdefault(key.lower(), [key])
        box.append(value)

    def extend(self, data):
        # type: (HttpHeaderStream) -> None
        seq = (
            data.items()
            if isinstance(data, MutableMapping)
            # pylint: disable=deprecated-typing-alias
            else cast(typing.Iterable[Tuple[str, str]], data)
            # pylint: enable=deprecated-typing-alias
        )
        for key, val in seq:
            self.add(key, val)

    def __contains__(self, key):
        # type: (str) -> bool
        return key.lower() in self._store

    def count_keys(self):
        # type: () -> int
        return len(self._store.keys())

    def count_items(self):
        # type: () ->  int
        return sum(1 for _ in self.items())

    def items(self):
        # type: () -> Iterator[tuple[str, Any]]
        for items in self._store.values():
            original_key = items[0]
            for idx, item in enumerate(items):
                if idx > 0:
                    yield original_key, item

    def __repr__(self):
        # type: () -> str
        return str(list(self.items()))
