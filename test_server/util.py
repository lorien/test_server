import warnings


class TestServerDeprecatedFeature(UserWarning):
    """
    Warning category used to generate warning message
    about deprecated feature of user_agent library.
    """


def warn(msg, stacklevel=2):
    warnings.warn(msg, category=TestServerDeprecatedFeature,
                  stacklevel=stacklevel)


class DeprecatedAttribute(object):
    def __init__(self, valid_name, msg):
        self.valid_name = valid_name
        self.msg = msg

    def __set__(self, obj, val):
        warn(self.msg, stacklevel=3)
        setattr(obj, self.valid_name, val)

    def __get__(self, obj, type=None): # pylint: disable=redefined-builtin
        warn(self.msg, stacklevel=3)
        return getattr(obj, self.valid_name)

    # pylint: disable=unexpected-special-method-signature
    def __del__(self, obj):
        warn(self.msg, stacklevel=3)
        delattr(obj, self.valid_name)
