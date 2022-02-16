===========
Test-server
===========

.. image:: https://travis-ci.org/lorien/test_server.png?branch=master
    :target: https://travis-ci.org/lorien/test_server

Simple HTTP Server for testing HTTP clients.


Installation
============

.. code:: bash

    pip install test-server


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
