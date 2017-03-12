.. _api_request:

Request object
==============

Request object is a dict with keys:

request :: args
^^^^^^^^^^^^^^^
    
    :type: :class:`dict`

    Query string arguments

request :: headers
^^^^^^^^^^^^^^^^^^

    :type: :class:`tornado.netutil.HTTPHeaders`

    HTTP headers

request :: cookies
^^^^^^^^^^^^^^^^^^

    :type: :class:`dict`

    The dict mapping cookie's names to their datas.
    Cookie data is a dict with keys: name, value, path, expires, etc.
    See possible keys at https://docs.python.org/2/library/cookie.html#morsel-objects

request :: path
^^^^^^^^^^^^^^^
    :type: :class:`str`

    The path fragment of the requested URL

request :: method
^^^^^^^^^^^^^^^^^

    :type: :class:`str`
    
    Method of HTTP request

request :: data
^^^^^^^^^^^^^^^

    :type: :class:`bytes`

    The data submitted with HTTP request

request :: files
^^^^^^^^^^^^^^^^
    
    :type: ???

    Files sent in request (in case of form/multipart-data).

request :: client_ip
^^^^^^^^^^^^^^^^^^^^

    :type: :class:`str`

    IP address of the client sent the request

request :: done
^^^^^^^^^^^^^^^

    :type: :class:`bool`

    The flag means if the request has been performed

request :: charset
^^^^^^^^^^^^^^^^^^^

    :type: :class:`str`


    The character set which data of request are encoded with. This is the only
    request parameter which is set by YOU and not by the server. If you expect
    the data from the client would be in non UTF-8 encoding then specify correct
    encoding with:

    ..  code:: python

        server.request['charset'] = '<encoding>'
