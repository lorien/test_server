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
    server.set_response('data', b'response-data')
    req = urlopen(server.get_url(), b'request-data')
    assert req.read() == b'response-data'
    assert server.get_request('data') == b'request-data'

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

You create TestServer instance. It creates files to exchange data with HTTP server, then starts new process that runs HTTP server. To set details of response or see details of request you work with TestServer instance as usual (as in thread mode).

API
---

.. toctree::
    :maxdepth: 2

    api_server


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
