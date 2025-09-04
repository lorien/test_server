# from __future__ import annotations

from threading import Lock

import pytest

# pylint: disable=import-error
from six.moves.collections_abc import Iterator

# pylint: enable=import-error
from typing_extensions import TypedDict

from test_server import TestServer

# pylint: disable=invalid-name
CacheDict = TypedDict("CacheDict", {"server": TestServer}, total=False)
# pylint: enable=invalid-name


CACHE = {}  # type: CacheDict
CACHE_LOCK = Lock()


@pytest.fixture(scope="session", name="global_server")
def fixture_global_server():
    # type: () -> Iterator[TestServer]
    with CACHE_LOCK:
        if "server" not in CACHE:
            srv = TestServer()
            srv.start()
            CACHE["server"] = srv
    yield CACHE["server"]
    with CACHE_LOCK:
        if CACHE["server"]:
            CACHE["server"].stop()
            del CACHE["server"]


@pytest.fixture(name="server")
def fixture_server(global_server):
    # type: (TestServer) -> TestServer
    global_server.reset()
    return global_server
