repoze.accelerator
==================

An caching accelerator for WSGI applications.  Intercepts responses
from downstream WSGI applications and caches responses based on
Cache-Control (and other) response header values.  Serves up cached
responses to clients thereafter based on the policy specified by the
headers.

Configuration via Python
------------------------

Configure the middleware via Python::

  import logging
  from repoze.accelerator.policy import AcceleratorPolicy
  from repoze.accelerator.storage import MemoryStorage
  from repoze.accelerator.middleware import AcceleratorMiddleware

  logger = logger.getLogger('repoze.accelerator')

  storage = MemoryStorage(logger)
  policy = AcceleratorPolicy(logger, storage)
  middleware = AcceleratorMiddleware(app, policy, logger)

Configuration via Paste Deploy
------------------------------

Configure the paste.ini file like so::

  [pipeline:main]
  pipeline = egg:Paste#cgitb
             egg:repoze.accelerator#accelerator
             myapp


The Default Policy
------------------

The default policy is the AcceleratorPolicy.  This policy has the
following features:

- Allow configuration of "vary" policies for both request headers
  and request environment values.

- Allow specification of "allowed methods"; requests which don't use
  one of these methods won't be served from cache.

- Allow specification of "honor_shift_reload": if Pragma: no-cache or
  Cache-Control: no-cache exists in the request, and this value is true,
  the response will not be served from cache even if it otherwise might
  have been.

- Allow specification of "store_https_responses".  If this is true,
  we will store https responses and some information provided by
  requests emitted via HTTPS.

When deciding whether we can fetch from our storage or not:

- If we honor shift-reload, and the request has a Pragma: no-cache
  or Cache-Control: no-cache associated with it, don't try to
  retrieve it from storage.

- If the request method doesn't match one of our allowed_methods,
  don't try to retrieve it from storage.

- If the request has a Range, header, don't try to retrieve it
  from storage.

- If the request is conditional (e.g. If-Modified-Since,
  If-None-Match), don't try to retrieve it from storage.

- Otherwise, attempt to retrieve it from storage.

When deciding whether a value returned from storage should be
checked for freshness:

- If one representation stored matches the request headers and
  environment, check it for freshness.

- Otherwise, abort.

To decide whether an item is fresh or not:

- If the entry in the cache is stale, don't serve from cache.
  Staleness is defined as having a CC: max-age < (now -
  entitydate) or an expires header whereby (expires - entitydate)
  < (now - entitydate).  Entities which don't have a Date header
  are also considered stale.

When deciding whether we can store response data in our storage:

- If the request method doesn't match one of our allowed_methods,
  don't store.

- If the response status is not 200 (OK) or 203 (Non-Authoritative
  Information), don't store.

- If the response has a Cache-Control header or a Pragma header,
  and either has 'no-cache' in its value, don't store.

- If the response has a Cache-Control header, and it has a max-age
  of 0 or a max-age we don't understand, don't store.

- If the request is an https request, and "store_https_responses" is false,
  don't store.

- If the response does not have a Date header, assume the date is now.

When storing data to storage:

- Store the status, the end-to-end headers in the response, and
  information about request header and environment variance.

Mea Culpa
---------

There is not nearly enough documentation here to be considered
canonical.  Apologies.  Please read the source for more info for now.

Reporting Bugs / Development Versions
-------------------------------------

Visit http://bugs.repoze.org to report bugs.  Visit
http://svn.repoze.org to download development or tagged versions.
