test_server documentation
=========================

.. module:: test_server.server

The test_server packages provides HTTP server that allows you:

* to see details of HTTP request
* to set parameters of HTTP response

Basic example:

.. code:: python

    from test_server import TestServer
    from six.moves.urllib.request import urlopen

    server = TestServer()
    server.start()
    server.set_response('data', b'response-data')
    req = urlopen(server.get_url(), b'request-data')
    assert req.read() == b'response-data'
    assert server.get_request('data') == b'request-data'

HTTP request details
--------------------

Parameter of request you can get access to. Each parameter is a key and
description. Use the key to get the data with :meth:`TestServer:get_request`

request:args
^^^^^^^^^^^^

:args (dict): query string arguments,
:headers (<`tornado.netutil.HTTPHeaders`>): HTTP headers
:cookies (<dict>): the dict mapping cookie's name to its data
                 Cookie data is a dict with keys: name, value,
                 path, expires, etc. See possible keys at https://docs.python.org/2/library/cookie.html#morsel-objects
:path (<str>): path part of request URL
:method <string>: method of HTTP request
:charset: charset of HTTP request, parsed from "Content-Type" header.
:data <bytes>: data part of HTTP request
:files (???): files sent in request (in case of form/multipart-data).
:client_ip <str>: IP address of the client sent the request
:done: the: False,

:foo: bar
:1: 2

* query string aruments
* headers
* cookies
* HTTP method
* files
* remote IP

Detail of response you can set:

* status code
* content
* headers
* cookies


The test_server can work in two modes: thread (default) and subprocess. In thread mode the actual test server runs in separate thread of the python process which created TestServer instance. In process mode the test server runs in seprate process (started with subprocess.Popen) and communicates with TestServer instance via files.

In both modes you create `TestServer` instance which controls the HTTP Server running in seperate thread (thread mode) or separate process (subprocess mode).

Thread mode
-----------


You create TestServer instance. It creates extra thread that runs the HTTP server. Your HTTP client works in the same process as the TestServer instance. If your client modifies somehow the standard python socket library then that could affect the test_server behaviour. To avoid this use test_server in subprocess mode.

Subprocess mode
---------------

You create TestServer instance. It creates files to exchange data with HTTP server, then starts new process that runs HTTP server. To set details of response or see details of request you work with TestServer instance as usual (as in thread mode).

API
---

.. toctree::
    :maxdepth: 2

    api_server
    api_util
    api_error


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
