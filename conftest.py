import pytest

def pytest_addoption(parser):
    parser.addoption('--engine', type=str, default='thread',
                     help='Method of running test HTTP server')


@pytest.fixture(scope='session')
def opt_engine(request):
    return request.config.getoption('--engine')
