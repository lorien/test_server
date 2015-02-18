===========
Test-server
===========

.. image:: https://travis-ci.org/lorien/test_server.png?branch=master
    :target: https://travis-ci.org/lorien/test_server

.. image:: https://coveralls.io/repos/lorien/test_server/badge.svg?branch=master
    :target: https://coveralls.io/r/lorien/test_server?branch=master

.. image:: https://pypip.in/download/test-server/badge.svg?period=month
    :target: https://pypi.python.org/pypi/test-server

.. image:: https://pypip.in/version/test-server/badge.svg
    :target: https://pypi.python.org/pypi/test-server

.. image:: https://landscape.io/github/lorien/test_server/master/landscape.png
   :target: https://landscape.io/github/lorien/test_server/master

HTTP Server to test HTTP clients.


Usage Example
=============

Example:

.. code:: python

    from unittest import TestCase
    try:
        from urllib import urlopen
    except ImportError:
        from urllib.request import urlopen
    from test_server import TestServer

    class UrllibTestCase(TestCase):
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
            token = b'zorro'
            self.server.response['data'] = token
            data = urlopen(self.server.base_url).read()
            self.assertEqual(data, token)


Installation
============

Run::

    pip install test-server


Dependencies
============

* tornado
