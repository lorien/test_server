.. _api_response:

Response object
===============

    :code: HTTP status code,
    :data: data part of HTTP response,
    :headers: HTTP headers,
    :cookies: cookies,
    :callback: function that builds completely custom request
    :sleep: amount of time to wait before send response data

Response object is a dict with keys:

response :: code
^^^^^^^^^^^^^^^^
    
    :type: :class:`int`

    HTTP status code

response :: data
^^^^^^^^^^^^^^^^

    :type: :class:`bytes`

    body of HTTP response

response :: headers
^^^^^^^^^^^^^^^^^^^

    :type: :class:`list`
    
    HTTP headers

response :: path
^^^^^^^^^^^^^^^
    :type: :class:`str`

    The path fragment of the requested URL

response :: cookies
^^^^^^^^^^^^^^^^^^^

    :type: :class:`list`

    Cookies
    
response :: callback
^^^^^^^^^^^^^^^^^^^^

    :type: `function`
    
    The function that builds custom response

response :: sleep
^^^^^^^^^^^^^^^^^
    
    :type: :class:`int`

    Time to wait before send data to HTTP client
