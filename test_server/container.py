from contextlib import contextmanager
from copy import deepcopy


class CallbackDict(object):
    """
    Dict-like class calling callbacks on data read/write.

    When data is reading the `.read_callback()` is called.
    When data is writing the `.write_callback()` is called.
    """

    def __init__(self, data=None):
        if data is None:
            self._reg = {}
        else:
            self._reg = deepcopy(data)
        self.callbacks_enabled = True

    def write_callback(self):
        pass

    def read_callback(self):
        pass

    def __getitem__(self, key):
        if self.callbacks_enabled:
            self.read_callback()
        return self._reg[key]

    def __setitem__(self, key, val):
        self._reg[key] = val
        if self.callbacks_enabled:
            self.write_callback()

    def __delitem__(self, key):
        del self._reg[key]
        if self.callbacks_enabled:
            self.write_callback()

    def update(self, data):
        self._reg.update(data)
        if self.callbacks_enabled:
            self.write_callback()

    def clear(self):
        self._reg.clear()
        if self.callbacks_enabled:
            self.write_callback()

    def _not_implemented_mock(self, *args, **kwargs):
        raise NotImplementedError

    get = set = keys = items = _not_implemented_mock

    @contextmanager
    def disable_callbacks(self):
        self.callbacks_enabled = False
        yield
        self.callbacks_enabled = True

    def get_dict(self):
        if self.callbacks_enabled:
            self.read_callback()
        return self._reg

    def __contains__(self, key):
        if self.callbacks_enabled:
            self.read_callback()
        return key in self._reg
