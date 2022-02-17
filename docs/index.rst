test_server documentation
=========================

.. module:: test_server.server

The test_server packages provides HTTP server that allows you:

* to see details of HTTP request
* to set parameters of HTTP response

Basic example:

.. code:: python

    from test_server import TestServer
    from urllib.request import urlopen

    server = TestServer()
    server.start()
    server.response['data'] = b'response-data')
    req = urlopen(server.get_url(), b'request-data')
    assert req.read() == b'response-data'
    assert server.request['data'] == b'request-data'


Request object
--------------

The request object contains information about HTTP request
sent from HTTP client to test server. The request
object has dict-like interface and provides these details:

    :args: query string arguments
    :headers: HTTP headers
    :cookies: cookies
    :path: the path fragmet of requested URL
    :method: HTTP method
    :data: data sent with the request
    :files: files sent with the request
    :client_ip: IP address the request has been sent from
    :done: the flag means if the request has been sent already
    :charset: the character set which data of request are encoded with

See detailed description of request properties at :ref:`api_request`


Response object
---------------

The response object controls the data which the HTTP client would
received in response from test server. Available keys are:

    :status: HTTP status code
    :data: data part of HTTP response
    :headers: HTTP headers
    :cookies: cookies
    :callback: function that builds completely custom request
    :sleep: amount of time to wait before send response data

See detailed description of response properties at :ref:`api_response`



API
---

.. toctree::
    :maxdepth: 2

    api_server
    api_util
    api_error
    api_request
    api_response


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
