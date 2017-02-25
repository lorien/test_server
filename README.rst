===========
Test-server
===========

.. image:: https://travis-ci.org/lorien/test_server.png?branch=master
    :target: https://travis-ci.org/lorien/test_server

.. image:: https://ci.appveyor.com/api/projects/status/o3qhdh1gprcu1x1x
    :target: https://ci.appveyor.com/project/lorien/test-server

.. image:: https://coveralls.io/repos/lorien/test_server/badge.svg?branch=master
    :target: https://coveralls.io/r/lorien/test_server?branch=master

.. image:: https://api.codacy.com/project/badge/Grade/3ff9f3ebf06d4b7f8809b264837eac43
   :target: https://www.codacy.com/app/lorien/test_server?utm_source=github.com&utm_medium=referral&utm_content=lorien/test_server&utm_campaign=badger


HTTP Server to test HTTP clients.


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
