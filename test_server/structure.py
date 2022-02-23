from pprint import pprint  # pylint: disable=unused-import
from collections import OrderedDict
from typing import (
    Union,
    Optional,
    Tuple,
    Mapping,
    MutableMapping,
    List,
    cast,
    Iterable,
)

__all__ = ["HttpHeaderStorage"]


HttpHeaderStream = Union[
    Mapping[str, str],
    Iterable[Tuple[str, str]],
]


class HttpHeaderStorage(object):
    """Storage for HTTP Headers.

    The storage maps string keys to one or multiple string values.
    Keys are case insensitive though the original case is stored.
    """

    def __init__(
        self, data: Optional[HttpHeaderStream] = None, charset: str = "utf-8"
    ) -> None:
        self._store: MutableMapping[str, List[str]] = OrderedDict()
        self._charset = charset
        if data is not None:
            self.extend(data)

    # Public Interface

    def set(self, key: str, value: str) -> None:
        # Store original case of key
        self._store[key.lower()] = [key, value]

    def get(self, key: str) -> str:
        return self._store[key.lower()][1]

    def getlist(self, key: str) -> List[str]:
        return self._store[key.lower()][1:]

    def remove(self, key: str):
        del self._store[key.lower()]

    def add(self, key: str, value: str):
        box = self._store.setdefault(key.lower(), [key])
        box.append(value)

    def extend(self, data: HttpHeaderStream) -> None:
        seq = (
            data.items()
            if isinstance(data, MutableMapping)
            else cast(Iterable[Tuple[str, str]], data)
        )
        for key, val in seq:
            self.add(key, val)

    def __contains__(self, key: str) -> bool:
        return key.lower() in self._store

    def count_keys(self) -> int:
        return len(self._store.keys())

    def count_items(self) -> int:
        return sum(1 for _ in self.items())

    def items(self):
        for items in self._store.values():
            original_key = items[0]
            for idx, item in enumerate(items):
                if idx > 0:
                    yield original_key, item

    def __repr__(self) -> str:
        return str(list(self.items()))
