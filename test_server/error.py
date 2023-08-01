__all__ = [
    "TestServerError",
    "WaitTimeoutError",
    "InternalError",
    "RequestNotProcessedError",
    "NoResponseError",
]


class TestServerError(Exception):
    """Base class for all errrors raised by test_server package."""

    __test__ = False  # for pytest ignore this class


class WaitTimeoutError(TestServerError):
    """Raised by wait_request method if timed out waiting a request done."""


class InternalError(TestServerError):
    """Raised when exception happens during the processing a request sent by client."""


class RequestNotProcessedError(TestServerError):
    """Raised by get_request method when no request has been processed."""


class NoResponseError(TestServerError):
    """Raised when no response data is configured to hande a request."""
