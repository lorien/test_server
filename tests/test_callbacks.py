from six.moves.urllib.request import urlopen

from .util import fixture_global_server, fixture_server  # pylint: disable=unused-import


def test_callback(server):
    def get_callback():
        return {
            "type": "response",
            "body": b"Hello",
            "headers": [
                ("method", "get"),
            ],
        }

    def post_callback():
        return {
            "type": "response",
            "body": b"World",
            "headers": [
                ("method", "post"),
            ],
        }

    server.response["callback"] = get_callback
    info = urlopen(server.get_url())
    assert info.headers["method"] == "get"
    assert info.read() == b"Hello"

    server.response["post.callback"] = post_callback
    info = urlopen(server.get_url(), b"key=val")
    assert info.headers["method"] == "post"
    assert info.read() == b"World"
