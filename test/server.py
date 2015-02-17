from unittest import TestCase
try:
    from urllib import urlopen
except ImportError:
    from urllib.request import urlopen
import time
import six

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

    def test_callback_wtf(self):
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

    def test_response_once_get(self):
        self.server.response['get'] = b'base'
        self.assertEquals(b'base', urlopen(self.server.base_url).read())

        self.server.response_once['get'] = b'tmp'
        self.assertEquals(b'tmp', urlopen(self.server.base_url).read())

        self.assertEquals(b'base', urlopen(self.server.base_url).read())

    def test_response_once_headers(self):
        self.server.response['headers'] = [('foo', 'bar')]
        info = urlopen(self.server.base_url)
        self.assertTrue(info.headers['foo'] == 'bar')

        self.server.response_once['headers'] = [('baz', 'gaz')]
        info = urlopen(self.server.base_url)
        self.assertTrue(info.headers['baz'] == 'gaz')
        self.assertFalse('foo' in info.headers)

        info = urlopen(self.server.base_url)
        self.assertFalse('baz' in info.headers)
        self.assertTrue(info.headers['foo'] == 'bar')

    def test_response_once_reset_headers(self):
        self.server.response_once['headers'] = [('foo', 'bar')]
        self.server.reset()
        info = urlopen(self.server.base_url)
        self.assertFalse('foo' in info.headers)

    def test_method_sleep(self):
        delay = 0.3

        start = time.time()
        urlopen(self.server.base_url)
        elapsed = time.time() - start
        self.assertFalse(elapsed > delay)

        self.server.sleep['get'] = delay
        start = time.time()
        urlopen(self.server.base_url)
        elapsed = time.time() - start
        self.assertTrue(elapsed > delay)

    def test_callback(self):
        def callback(self):
            self.set_header('foo', 'bar')
            self.write(b'Hello')
            self.finish()

        self.server.response['get_callback'] = callback
        info = urlopen(self.server.base_url)
        self.assertTrue(info.headers['foo'] == 'bar')
        self.assertEqual(info.read(), b'Hello')

        self.server.response['post_callback'] = callback
        info = urlopen(self.server.base_url, b'key=val')
        self.assertTrue(info.headers['foo'] == 'bar')
        self.assertEqual(info.read(), b'Hello')

    def test_response_once_code(self):
        info = urlopen(self.server.base_url)
        self.assertEqual(info.getcode(), 200)

        self.server.response_once['code'] = 403
        if six.PY2:
            info = urlopen(self.server.base_url)
            self.assertEqual(info.getcode(), 403)
        else:
            from urllib.error import HTTPError
            self.assertRaises(HTTPError, urlopen, self.server.base_url)

        info = urlopen(self.server.base_url)
        self.assertEqual(info.getcode(), 200)

    def test_response_once_cookies(self):
        self.server.response['cookies'] = {'foo': 'bar'}
        info = urlopen(self.server.base_url)
        self.assertTrue('foo=bar' in info.headers['Set-Cookie'])

        self.server.response_once['cookies'] = {'baz': 'gaz'}
        info = urlopen(self.server.base_url)
        self.assertFalse('foo=bar' in info.headers['Set-Cookie'])
        self.assertTrue('baz=gaz' in info.headers['Set-Cookie'])

        info = urlopen(self.server.base_url)
        self.assertTrue('foo=bar' in info.headers['Set-Cookie'])
        self.assertFalse('baz=gaz' in info.headers['Set-Cookie'])

    def test_response_content_callable(self):
        self.server.response['get'] = lambda: b'Hello'
        info = urlopen(self.server.base_url)
        self.assertEqual(info.read(), b'Hello')

    def test_timeout_iterator(self):
        delays = (0.5, 0.3, 0.1)
        self.server.timeout_iterator = iter(delays)

        for delay in delays:
            start = time.time()
            urlopen(self.server.base_url)
            elapsed = time.time() - start
            self.assertTrue(elapsed > delay)
