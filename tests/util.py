from __future__ import annotations

from collections.abc import Generator
from threading import Lock

import pytest
from typing_extensions import TypedDict

from test_server import TestServer


class CacheDict(TypedDict, total=False):
    server: TestServer


CACHE: CacheDict = {}
CACHE_LOCK = Lock()


@pytest.fixture(scope="session", name="global_server")
def fixture_global_server() -> Generator[TestServer, None, None]:
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
def fixture_server(global_server: TestServer) -> TestServer:
    global_server.reset()
    return global_server
