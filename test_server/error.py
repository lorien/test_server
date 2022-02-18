__all__ = ["TestServerError", "WaitTimeoutError", "InternalError"]


class TestServerError(Exception):
    pass


class WaitTimeoutError(TestServerError):
    pass


class InternalError(TestServerError):
    pass
