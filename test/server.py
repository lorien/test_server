from unittest import TestCase
from six.moves.urllib.request import urlopen
from six.moves.urllib.error import HTTPError
import time

from test_server import TestServer
import test_server


class ServerTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = TestServer()
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self.server.reset()

    def test_get(self):
        self.server.response['data'] = b'zorro'
        data = urlopen(self.server.get_url()).read()
        self.assertEqual(data, self.server.response['data'])

    def test_path(self):
        urlopen(self.server.get_url('/foo')).read()
        self.assertEqual(self.server.request['path'], '/foo')

        urlopen(self.server.get_url('/foo?bar=1')).read()
        self.assertEqual(self.server.request['path'], '/foo')
        self.assertEqual(self.server.request['args']['bar'], '1')

    def test_post(self):
        self.server.response['post.data'] = b'foo'
        data = urlopen(self.server.get_url(), b'THE POST').read()
        self.assertEqual(data, self.server.response['post.data'])

    def test_data_iterator(self):
        class ContentGenerator(object):
            def __init__(self):
                self.count = 0

            def __iter__(self):
                return self

            def next(self):
                self.count += 1
                return 'foo'

            __next__ = next

        gen = ContentGenerator()
        self.server.response['get.data'] = gen
        urlopen(self.server.get_url()).read()
        self.assertEqual(gen.count, 1)
        urlopen(self.server.get_url()).read()
        self.assertEqual(gen.count, 2)
        # Now create POST request which should no be
        # processed with ContentGenerator which is bind to GET
        # requests
        urlopen(self.server.get_url(), b'some post').read()
        self.assertEqual(gen.count, 2)

    def test_data_generator(self):
        def gen():
            yield b'one'
            yield b'two'

        self.server.response['get.data'] = gen()
        self.assertEquals(b'one', urlopen(self.server.get_url()).read())
        self.assertEquals(b'two', urlopen(self.server.get_url()).read())
        self.assertRaises(HTTPError, urlopen, self.server.get_url())

    def test_response_once_get(self):
        self.server.response['data'] = b'base'
        self.assertEquals(b'base', urlopen(self.server.get_url()).read())

        self.server.response_once['data'] = b'tmp'
        self.assertEquals(b'tmp', urlopen(self.server.get_url()).read())

        self.assertEquals(b'base', urlopen(self.server.get_url()).read())

    def test_response_once_headers(self):
        self.server.response['headers'] = [('foo', 'bar')]
        info = urlopen(self.server.get_url())
        self.assertTrue(info.headers['foo'] == 'bar')

        self.server.response_once['headers'] = [('baz', 'gaz')]
        info = urlopen(self.server.get_url())
        self.assertTrue(info.headers['baz'] == 'gaz')
        self.assertFalse('foo' in info.headers)

        info = urlopen(self.server.get_url())
        self.assertFalse('baz' in info.headers)
        self.assertTrue(info.headers['foo'] == 'bar')

    def test_response_once_reset_headers(self):
        self.server.response_once['headers'] = [('foo', 'bar')]
        self.server.reset()
        info = urlopen(self.server.get_url())
        self.assertFalse('foo' in info.headers)

    def test_method_sleep(self):
        delay = 0.3

        start = time.time()
        urlopen(self.server.get_url())
        elapsed = time.time() - start
        self.assertFalse(elapsed > delay)

        self.server.response['sleep'] = delay
        start = time.time()
        urlopen(self.server.get_url())
        elapsed = time.time() - start
        self.assertTrue(elapsed > delay)

    def test_callback(self):
        def get_callback(self):
            self.set_header('method', 'get')
            self.write(b'Hello')
            self.finish()

        def post_callback(self):
            self.set_header('method', 'post')
            self.write(b'Hello')
            self.finish()

        self.server.response['callback'] = get_callback
        info = urlopen(self.server.get_url())
        self.assertTrue(info.headers['method'] == 'get')
        self.assertEqual(info.read(), b'Hello')

        self.server.response['post.callback'] = post_callback
        info = urlopen(self.server.get_url(), b'key=val')
        self.assertTrue(info.headers['method'] == 'post')
        self.assertEqual(info.read(), b'Hello')

    def test_response_once_code(self):
        info = urlopen(self.server.get_url())
        self.assertEqual(info.getcode(), 200)

        self.server.response_once['code'] = 403
        self.assertRaises(HTTPError, urlopen, self.server.get_url())

        info = urlopen(self.server.get_url())
        self.assertEqual(info.getcode(), 200)

    def test_response_once_cookies(self):
        self.server.response['cookies'] = [('foo', 'bar')]
        info = urlopen(self.server.get_url())
        self.assertTrue('foo=bar' in info.headers['Set-Cookie'])

        self.server.response_once['cookies'] = [('baz', 'gaz')]
        info = urlopen(self.server.get_url())
        self.assertFalse('foo=bar' in info.headers['Set-Cookie'])
        self.assertTrue('baz=gaz' in info.headers['Set-Cookie'])

        info = urlopen(self.server.get_url())
        self.assertTrue('foo=bar' in info.headers['Set-Cookie'])
        self.assertFalse('baz=gaz' in info.headers['Set-Cookie'])

    def test_timeout_iterator(self):
        delays = (0.5, 0.3, 0.1)
        self.server.timeout_iterator = iter(delays)

        for delay in delays:
            start = time.time()
            urlopen(self.server.get_url())
            elapsed = time.time() - start
            self.assertTrue(elapsed > delay)

    def test_default_header_content_type(self):
        info = urlopen(self.server.get_url())
        self.assertEquals(info.headers['content-type'],
                          'text/html; charset=UTF-8')

    def test_custom_header_content_type(self):
        self.server.response['headers'] = [
            ('Content-Type', 'text/html; charset=koi8-r')]
        info = urlopen(self.server.get_url())
        self.assertEquals(info.headers['content-type'],
                          'text/html; charset=koi8-r')

    def test_default_header_server(self):
        info = urlopen(self.server.get_url())
        self.assertEquals(info.headers['server'],
                          'TestServer/%s' % test_server.version)

    def test_custom_header_server(self):
        self.server.response['headers'] = [
            ('Server', 'Google')]
        info = urlopen(self.server.get_url())
        self.assertEquals(info.headers['server'], 'Google')



class ServerMultStartStopTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = TestServer()
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self.server.reset()

    def test_basic(self):
        self.server.response['data'] = b'zorro'
        data = urlopen(self.server.get_url()).read()
        self.assertEqual(data, self.server.response['data'])


class ServerMultiStartStopTestCase(TestCase):
    def test_multiple_start_stop_cycles(self):
        for x in range(30):
            server = TestServer()
            server.start()
            server.response['data'] = b'zorro'
            for y in range(10):
                data = urlopen(server.get_url()).read()
                self.assertEqual(data, server.response['data'])
            server.stop()


class ExtraPortsTestCase(TestCase):
    port = 9876
    extra_ports = [9875, 9874]

    @classmethod
    def setUpClass(cls):
        cls.server = TestServer(port=cls.port, extra_ports=cls.extra_ports)
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self.server.reset()

    def test_basic(self):
        self.server.response['data'] = b'zorro'
        for port in [self.port] + self.extra_ports:
            data = urlopen(self.server.get_url(port=port)).read()
            self.assertEqual(data, self.server.response['data'])
