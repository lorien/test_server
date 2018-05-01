import pytest

from test_server import TestServer

STATE = {
    'server': None
}


@pytest.fixture(scope='session')
def global_server():
    if not STATE['server']:
        print('[!] Starting server')
        server = TestServer(port=9999)
        server.start(daemon=True)
        STATE['server'] = server
    yield STATE['server']
    if STATE['server']:
        print('[!] Stoping server')
        STATE['server'].stop()
        STATE['server'] = None


@pytest.fixture(scope='function')
def server(global_server):
    global_server.reset()
    return global_server
