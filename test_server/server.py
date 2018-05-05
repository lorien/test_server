# Copyright 2015-2018 Gregory Petukhov (lorien@lorien.name)
# *
# Licensed under the MIT License
import logging
from threading import Thread, Event
import time
import types
from six.moves.urllib.parse import urljoin
from collections import defaultdict, Iterable

import six
from webtest.http import StopableWSGIServer
from waitress import task
import bottle

from test_server.error import TestServerError

__all__ = ('TestServer', 'WaitTimeoutError')
logger = logging.getLogger('test_server.server') # pylint: disable=invalid-name

if six.PY3:
    # Original (from waitress.compat.tobytes):
    # def tobytes(s):
    #    return bytes(s, 'latin-1')
    task.tobytes = lambda x: bytes(x, 'utf-8')


def _hval_custom(value):
    value = bottle.tonat(value)
    if '\n' in value or '\r' in value:# or '\0' in value:
        raise ValueError(
            'Header value must not contain control characters: %r' % value
        )
    return value


bottle._hval_origin = bottle._hval # pylint: disable=protected-access
bottle._hval = _hval_custom # pylint: disable=protected-access



class WaitTimeoutError(Exception):
    pass


def bytes_to_unicode(obj, charset):
    if isinstance(obj, six.text_type):
        return obj
    elif isinstance(obj, six.binary_type):
        return obj.decode(charset)
    elif isinstance(obj, list):
        return [bytes_to_unicode(x, charset) for x in obj]
    elif isinstance(obj, tuple):
        return tuple(bytes_to_unicode(x, charset) for x in obj)
    elif isinstance(obj, dict):
        return dict(bytes_to_unicode(x, charset) for x in obj.items())
    else:
        return obj


class WebApplication(bottle.Bottle):
    # pylint: disable=abstract-method,protected-access
    def __init__(self, test_server):
        self._server = test_server
        super(WebApplication, self).__init__()

    def get_param(self, key, method='get', clear_once=True):
        method_key = '%s.%s' % (method, key)

        if method_key in self._server.response_once:
            value = self._server.response_once[method_key]
            if clear_once:
                del self._server.response_once[method_key]
            return value
        elif key in self._server.response_once:
            value = self._server.response_once[key]
            if clear_once:
                del self._server.response_once[key]
            return value
        elif method_key in self._server.response:
            return self._server.response[method_key]
        elif key in self._server.response:
            return self._server.response[key]
        else:
            raise TestServerError('Parameter %s does not exists in '
                                  'server response data' % key)

    ## pylint: disable=arguments-differ
    #def decode_argument(self, value, **kwargs):
    #    # pylint: disable=unused-argument
    #    return value.decode(self._server.request['charset'])

    def handle_any_request(self, path):
        from test_server import __version__
        from bottle import request, LocalResponse

        method = request.method.lower()

        sleep = self.get_param('sleep', method)
        if sleep:
            time.sleep(sleep)
        self._server.request['client_ip'] = (
            request.environ.get('REMOTE_ADDR')
        )
        self._server.request['args'] = {}
        self._server.request['args_binary'] = {}
        for key in request.params.keys(): # pylint: disable=no-member
            self._server.request['args'][key] = (
                request.params.getunicode(key) # pylint: disable=no-member
            )
            #self._server.request['args_binary'][key] = request.params[key]
        self._server.request['headers'] = request.headers

        path = request.fullpath
        if isinstance(path, six.binary_type):
            path = path.decode('utf-8')
        self._server.request['path'] = path
        self._server.request['method'] = method.upper()

        cookies = {}
        for key, value in request.cookies.items(): # pylint: disable=no-member
            cookies[key] = {}
            cookies[key]['name'] = key
            cookies[key]['value'] = value
        self._server.request['cookies'] = cookies

        self._server.request['data'] = (
            request.body.read() # pylint: disable=no-member
        )
        self._server.request['files'] = defaultdict(list)
        for file_ in request.files.values(): # pylint: disable=no-member
            self._server.request['files'][file_.name].append({
                'name': file_.name,
                'raw_filename': file_.raw_filename,
                'content_type': file_.content_type,
                'filename': file_.filename,
                'content': file_.file.read(),
            })

        callback = self.get_param('callback', method)
        if callback:
            res = callback()
            if not isinstance(res, types.GeneratorType):
                res = [res]
            for item in res:
                assert (
                    isinstance(item, dict)
                    and 'type' in item
                    and item['type'] in ('response',)
                )
                bottle_res = LocalResponse()
                if item['type'] == 'response':
                    assert all(
                        x in ('type', 'status', 'headers',
                              'cookies', 'body')
                        for x in item.keys()
                    )
                    if 'status' in item:
                        bottle_res.status = item['status']
                    if 'headers' in item:
                        for key, val in item['headers']:
                            bottle_res.add_header(key, val)
                    if 'cookies' in item:
                        for key, val in item['cookies']:
                            bottle_res.set_cookie(key, val)
                    if 'body' in item:
                        # use list `[foo]`, see comments below
                        bottle_res.body = [item['body']]
            self._server.request['done'] = True
            return bottle_res
        else:
            response = {
                'code': 200,
                'headers': [],
                'data': b'',
            }

            response['code'] = self.get_param('code', method)

            for key, val in self.get_param('cookies', method):
                # Set-Cookie: name=newvalue; expires=date;
                # path=/; domain=.example.org.
                response['headers'].append(
                    ('Set-Cookie', '%s=%s' % (key, val)))

            for key, value in self.get_param('headers', method):
                response['headers'].append((key, value))

            response['headers'].append(
                ('Listen-Port', str(self._server.port)))

            data = self.get_param('data', method)
            if isinstance(data, six.string_types):
                response['data'] = data
            elif isinstance(data, six.binary_type):
                response['data'] = data
            elif isinstance(data, Iterable):
                try:
                    response['data'] = next(data)
                except StopIteration:
                    response['code'] = 503
            else:
                raise TestServerError('Data parameter should '
                                      'be string or iterable '
                                      'object')

            header_keys = [x[0].lower() for x in response['headers']]
            if 'content-type' not in header_keys:
                response['headers'].append(
                    ('Content-Type', 'text/html; charset=%s'
                     % self._server.response['charset'])
                )
            if 'server' not in header_keys:
                response['headers'].append(
                    ('Server', 'TestServer/%s' % __version__))

            bottle_response = LocalResponse()
            bottle_response.status = response['code']
            # Use list because if use just scalar object
            # then on python3 there is an strange error
            # unsupported response type int
            bottle_response.body = [response['data']]
            for key, val in response['headers']:
                bottle_response.add_header(key, val)
            self._server.request['done'] = True
            return bottle_response


class TestServer(object):
    def __init__(self, port=0, address='127.0.0.1'):
        self.request = {}
        self.response = {}
        self.response_once = {}
        self.port = port
        self.address = address
        self._handler = None
        self._thread = None
        self._server = None
        self._started = Event()
        self.config = {}
        self.config.update({
            'port': self.port,
        })
        self.reset()

    def reset(self):
        self.request.clear()
        self.request.update({
            'args': {},
            'args_binary': {},
            'headers': {},
            'cookies': None,
            'path': None,
            'method': None,
            'data': None,
            'files': {},
            'client_ip': None,
            'done': False,
            'charset': 'utf-8',
        })
        self.response.clear()
        self.response.update({
            'code': 200,
            'data': '',
            'headers': [],
            'cookies': [],
            'callback': None,
            'sleep': None,
            'charset': 'utf-8',
        })
        self.response_once.clear()

    def _build_web_app(self):
        """Build bottle web application that is served by HTTP server"""
        app = WebApplication(self)
        app.route('<path:re:.*>', method='ANY')(app.handle_any_request)
        return app

    def server_thread(self, server_created):
        """Ask HTTP server start processing requests

        This function is supposed to be run in separate thread.
        """

        # pylint: disable=line-too-long
        # params: https://github.com/Pylons/waitress/blob/master/waitress/adjustments.py#L79
        self._server = StopableWSGIServer(
            host=self.address,
            port=self.port,
            threads=1,
            expose_tracebacks=False,#True,
            application=self._build_web_app()
        )
        server_created.set()
        self._server.run()

    def start(self, daemon=True):
        """Start the HTTP server."""
        server_created = Event()
        self._thread = Thread(
            target=self.server_thread,
            args=[server_created]
        )
        self._thread.daemon = daemon
        self._thread.start()
        if not server_created.wait(2):
            raise Exception('Could not create test server app instance')
        self._server.wait()

    def stop(self):
        """Stop tornado loop and wait for thread finished it work."""
        self._server.shutdown()
        self._thread.join()

    def get_url(self, path='', port=None):
        """Build URL that is served by HTTP server."""
        if port is None:
            port = self.port
        return urljoin('http://%s:%d/' % (self.address, port), path)

    def wait_request(self, timeout):
        """Stupid implementation that eats CPU."""
        start = time.time()
        while True:
            if self.request['done']:
                break
            time.sleep(0.01)
            if time.time() - start > timeout:
                raise WaitTimeoutError('No request processed in %d seconds'
                                       % timeout)
