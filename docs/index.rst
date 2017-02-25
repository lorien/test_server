test_server documentation
=========================

The test_server packages provides HTTP server that allows you:

* to see details of HTTP request
* to set parameters of HTTP response

Basic example:

.. code:: python

    from test_server import TestServer
    from six.moves.urllib.request import urlopen

    server = TestServer()
    server.start()
    server.response['data'] = b'response-data'
    req = urlopen(server.get_url(), b'request-data')
    assert req.read() == b'response-data'
    assert server.request['data'] == b'request-data'

Details of request you can get access to:

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

You create TestServer instance. It creates files to exchange data with HTTP server, then starts new process that runs HTTP server. To set details of response or see details of request you work with TestServer instance as usual (as in thread mode). The only exception is that you have to call `load_request_state()` to sync TestServer.request object with request details storing in the separate process. The same issues is with setting the response details. After you changed the `response` object you have to call `save_response_state()` to push changes to the HTTP server process. To avoid explicit loading and saving the state just use `set_response()` method instead of `response` attribute and `get_request` method instead of `request` attrubute. For example, the `.set_response('data', b'foo')` is equal to `.response['data'] = b'foo'; save_response_state`.

Contents:

.. toctree::
   :maxdepth: 2


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
