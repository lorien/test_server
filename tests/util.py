import pytest

from test_server import TestServer

STATE = {"server": None}


@pytest.fixture(scope="session", name="global_server")
def fixture_global_server():
    if not STATE["server"]:
        srv = TestServer(port=9998)
        srv.start(daemon=True)
        STATE["server"] = srv
    yield STATE["server"]
    if STATE["server"]:
        STATE["server"].stop()
        STATE["server"] = None


@pytest.fixture(scope="function", name="server")
def fixture_server(global_server):
    global_server.reset()
    return global_server
