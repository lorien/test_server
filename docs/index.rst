test_server documentation
=========================

Package test_servers helps you to test HTTP clients:

* see details of HTTP request made by client
* serve to client custom HTTP response

Basic example:

.. code:: python

    from test_server import TestServer, Response
    from urllib.request import urlopen

    server = TestServer()
    server.start()
    server.add_response(Response(data=b'response-data'))
    req = urlopen(server.get_url(), b'request-data')
    assert req.read() == b'response-data'
    assert server.get_request().data == b'request-data'


Request object
--------------

The request object contains information about HTTP request sent by HTTP client
to test_server. The request object has these attrirubtes:

    :args: query string arguments
    :headers: HTTP headers
    :cookies: cookies
    :path: the path fragmet of requested URL
    :method: HTTP method
    :data: body of request
    :files: files sent with the request
    :client_ip: IP address the request has been sent from
    :charset: the character set which data of request are encoded with


Response object
---------------

The response object controls the data which the HTTP client would
received in response from test server. Available keys are:

    :callback: function that builds completely custom request
    :raw_callback: function that returns complete HTTP response as bytes blob
    :cookies: cookies
    :data: body of HTTP response
    :headers: HTTP headers
    :sleep: amount of time to wait before send response data
    :status: HTTP status code


API
---

.. toctree::
    :maxdepth: 2

    api_server
    api_error


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
