__all__ = [
    "TestServerError",
    "WaitTimeoutError",
    "InternalError",
    "RequestNotProcessed",
    "NoResponse",
]


class TestServerError(Exception):
    pass


class WaitTimeoutError(TestServerError):
    pass


class InternalError(TestServerError):
    pass


class RequestNotProcessed(TestServerError):
    pass


class NoResponse(TestServerError):
    pass
