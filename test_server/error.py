__all__ = ('TestServerError', 'TestServerRuntimeError')


class TestServerError(Exception):
    pass


class TestServerRuntimeError(TestServerError):
    pass
