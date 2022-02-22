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
    Mapping[str, Union[str, bytes]],
    Iterable[Tuple[str, Union[str, bytes]]],
]


class HttpHeaderStorage(object):
    """Storage for HTTP Headers.

    The storage maps string keys to byte values.
    String values are accepted alse and converted to bytes.
    One key might point to multiple values.
    Keys are case insensitive though the original case is stored.
    """

    def __init__(
        self, data: Optional[HttpHeaderStream] = None, charset: str = "utf-8"
    ) -> None:
        self._store: MutableMapping[str, List[Union[str, bytes]]] = OrderedDict()
        self._charset = charset
        if data is not None:
            self.extend(data)

    def _normalize_bytes_value(self, val: Union[str, bytes]):
        if isinstance(val, str):
            return val.encode(self._charset)
        else:
            return val

    # Public Interface

    def set(self, key: str, value: Union[str, bytes]) -> None:
        # Store original case of key
        self._store[key.lower()] = [key, self._normalize_bytes_value(value)]

    def get(self, key: str) -> bytes:
        return cast(bytes, self._store[key.lower()][1])

    def getlist(self, key: str) -> List[bytes]:
        return cast(List[bytes], self._store[key.lower()][1:])

    def remove(self, key: str):
        del self._store[key.lower()]

    def add(self, key: str, value: Union[str, bytes]):
        box = self._store.setdefault(key.lower(), [key])
        box.append(self._normalize_bytes_value(value))

    def extend(self, data: HttpHeaderStream) -> None:
        seq = (
            data.items()
            if isinstance(data, MutableMapping)
            else cast(Iterable[Tuple[str, Union[str, bytes]]], data)
        )
        for key, val in seq:
            self.add(key, self._normalize_bytes_value(val))

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
