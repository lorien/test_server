from unittest import TestCase
try:
    from urllib import urlopen
except ImportError:
    from urllib.request import urlopen

from test_server import TestServer


class TestTornadoServer(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = TestServer()
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self.server.reset()

    def tearDown(self):
        pass

    def test_get(self):
        self.server.response['get'] = b'zorro'
        data = urlopen(self.server.base_url).read()
        self.assertEqual(data, self.server.response['get'])

    def test_path(self):
        urlopen(self.server.base_url + '/foo').read()
        self.assertEqual(self.server.request['path'], '/foo')

        urlopen(self.server.base_url + '/foo?bar=1').read()
        self.assertEqual(self.server.request['path'], '/foo')
        self.assertEqual(self.server.request['args']['bar'], '1')

    def test_post(self):
        self.server.response['post'] = b'foo'
        data = urlopen(self.server.base_url, b'THE POST').read()
        self.assertEqual(data, self.server.response['post'])

    def test_callback(self):
        class ContentGenerator():
            def __init__(self):
                self.count = 0

            def __call__(self):
                self.count += 1
                return 'foo'

        gen = ContentGenerator()
        self.server.response['get'] = gen
        urlopen(self.server.base_url).read()
        self.assertEqual(gen.count, 1)
        urlopen(self.server.base_url).read()
        self.assertEqual(gen.count, 2)
        # Now create POST request which should no be
        # processed with ContentGenerator which is bind to GET
        # requests
        urlopen(self.server.base_url, b'some post').read()
        self.assertEqual(gen.count, 2)
