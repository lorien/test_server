__all__ = [
    "TestServerError",
    "WaitTimeoutError",
    "InternalError",
    "RequestNotProcessed",
    "NoResponse",
]


class TestServerError(Exception):
    """Base class for all errrors which belogns to test_server package"""


class WaitTimeoutError(TestServerError):
    """Raised by wait_request method if it timed out waiting a request done"""


class InternalError(TestServerError):
    """Raised when exception happens during the processing request sent by client"""


class RequestNotProcessed(TestServerError):
    """Raised by get_request method when no request has been processed"""


class NoResponse(TestServerError):
    """Raised by get_response method when no response data is available
    to hande the request"""
