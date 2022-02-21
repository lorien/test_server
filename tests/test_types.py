from typing import Mapping, MutableMapping, Dict


def test_dict():
    box = {}
    assert isinstance(box, Mapping)
    assert isinstance(box, MutableMapping)
    assert isinstance(box, Dict)
    assert isinstance(box, dict)


def test_mapping_instance():
    class Box(MutableMapping):  # pragma: no cover
        def __delitem__(self, key):
            pass

        def __getitem__(self, key):
            pass

        def __setitem__(self, key, val):
            pass

        def __iter__(self):
            return iter([])

        def __len__(self):
            return 0

    box = Box()
    assert isinstance(box, Mapping)
    assert isinstance(box, MutableMapping)
    assert not isinstance(box, Dict)
    assert not isinstance(box, dict)
