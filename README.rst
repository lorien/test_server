===========
Test-server
===========

.. image:: https://travis-ci.org/lorien/test_server.png?branch=master
    :target: https://travis-ci.org/lorien/test_server

Simple HTTP Server for testing HTTP clients.


Installation
============

.. code:: bash

    pip install test_server


Usage Example
=============

Example:

.. code:: python

   from unittest import TestCase
   import unittest
   from urllib.request import urlopen

   from test_server import TestServer, Response, HttpHeaderStorage


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
           self.server.add_response(
               Response(
                   data=b"hello",
                   headers={"foo": "bar"},
               )
           )
           self.server.add_response(Response(data=b"zzz"))
           url = self.server.get_url()
           info = urlopen(url)
           self.assertEqual(b"hello", info.read())
           self.assertEqual("bar", info.headers["foo"])
           info = urlopen(url)
           self.assertEqual(b"zzz", info.read())
           self.assertTrue("bar" not in info.headers)


   unittest.main()
