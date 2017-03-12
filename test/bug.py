# Copyright 2015-2017 Gregory Petukhov (lorien@lorien.name)
# *
# Licensed under the MIT License
# pylint: disable=redefined-outer-name
import pytest

from test_server import WaitTimeoutError
# pylint: disable=unused-import
from .server import global_server, server # noqa
# pylint: enable=unused-import


@pytest.mark.bug # noqa
def test_wait_timeout_error(server):
    """Need many iterations to be sure"""
    for _ in range(1000):
        with pytest.raises(WaitTimeoutError):
            server.wait_request(0.01)
