from pprint import pprint  # pylint: disable=unused-import
from collections import OrderedDict
from typing import (
    Union,
    Optional,
    Tuple,
    Mapping,
    MutableMapping,
    List,
    Iterator,
    cast,
    Iterable,
)

__all__ = ["HttpHeadersDict"]


StrOrBytes = Union[str, bytes]
MappingData = Union[
    Mapping[str, StrOrBytes],
    Iterable[Tuple[str, StrOrBytes]],
]


class HttpHeadersDict(MutableMapping):
    """Structure that maps str keys to str/bytes values

    If key points to multiple values these values are joined when value
    of key is requested.

    When key is requested its value/values are converted to bytes.
    """

    def __init__(
        self, data: Optional[MappingData] = None, charset: str = "utf-8"
    ) -> None:
        self._store: MutableMapping[str, List[Union[str, bytes]]] = OrderedDict()
        self._charset = charset
        if data is not None:
            self.update(data)

    def __setitem__(self, key: str, value: StrOrBytes) -> None:
        # Remember original form of key i.e. the case
        # Store values as bytes, convert str values into bytes if needed
        if isinstance(value, str):
            bytes_value = value.encode(self._charset)
        else:
            bytes_value = value
        self._store[key.lower()] = [key, bytes_value]

    def __getitem__(self, key: str) -> bytes:
        return b", ".join(
            x.encode(self._charset) if isinstance(x, str) else x
            for x in self._store[key.lower()][1:]
        )

    def __delitem__(self, key: str) -> None:
        del self._store[key.lower()]

    def __iter__(self) -> Iterator[str]:
        return (cast(str, x[0]) for x in self._store.values())

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return str(dict(self.items()))

    def add(self, key: str, value: StrOrBytes):
        box = self._store.setdefault(key.lower(), [key])
        box.append(value)

    def extend(self, data: MappingData) -> None:
        if isinstance(data, MutableMapping):
            for key, val in data.items():
                self.add(key, val)
        else:
            for key, val in cast(Iterable[Tuple[str, Union[str, bytes]]], data):
                self.add(key, val)
