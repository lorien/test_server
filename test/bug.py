#import pytest
#
#from .server import global_server, server
#
#@pytest.mark.bug
#def test_wait_timeout_error(server):
#    """Need many iterations to be sure"""
#    1/0
#    #while True:
#    #    with pytest.raises(WaitTimeoutError):
#    #        server.wait_request(0.01)
