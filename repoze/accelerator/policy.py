import calendar
from email.Utils import parsedate_tz
import time

from paste.request import construct_url
from paste.request import parse_headers
from paste.response import header_value

from zope.interface import implements
from zope.interface import directlyProvides

from repoze.accelerator.interfaces import IPolicy
from repoze.accelerator.interfaces import IPolicyFactory

class NullPolicy:
    """ Pass-through, caches nothing.
    """
    implements(IPolicy)

    def __init__(self):
        pass

    def fetch(self, environ):
        return None

    def store(self, status, headers, environ):
        pass

def make_null_policy(logger, storage, config):
    return NullPolicy()
directlyProvides(make_null_policy, IPolicyFactory)

class AcceleratorPolicy:
    """ Simple accelerating cache policy.

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

    """
    implements(IPolicy)

    def __init__(self,
                 logger,
                 storage,
                 allowed_methods=('GET',),
                 always_vary_on_headers=(),
                 always_vary_on_environ=('REQUEST_METHOD',),
                 honor_shift_reload=True,
                 store_https_responses=False,
                 ):
        self.logger = logger
        self.storage = storage
        self.allowed_methods = allowed_methods
        self.always_vary_on_headers = always_vary_on_headers
        self.always_vary_on_environ = always_vary_on_environ
        self.honor_shift_reload = honor_shift_reload
        self.store_https_responses = store_https_responses

    def fetch(self, environ):
        if environ.get('REQUEST_METHOD', 'GET') not in self.allowed_methods:
            return

        request_headers = list(parse_headers(environ))

        # if a Cache-Control/Pragma: no-cache header is in the request,
        # and if honor_shift_reload is true, we don't serve it from cache
        if self.honor_shift_reload:
            if self._check_no_cache(request_headers, environ):
                return
        # we don't try to serve range requests up from the cache
        if header_value(request_headers, 'Range'):
            return
        # we don't try to serve conditional requests up from cache
        for conditional in ('If-Modified-Since', 'If-None-Match',
                            'If-Match'):  # XXX other conditionals?
            if header_value(request_headers, conditional):
                return

        url = construct_url(environ)
        entries = self.storage.fetch(url)

        if entries:
            matching = self._discriminate(entries, request_headers, environ)
            if not matching:
                return

            now = time.time()

            discrims, expires, status, response_headers, body, extras = matching
            if expires > now:
                return status, response_headers, body

    def store(self, status, response_headers, environ):
        request_headers = list(parse_headers(environ))

        # abort if we shouldn't store this response
        request_method = environ.get('REQUEST_METHOD', 'GET')
        if request_method not in self.allowed_methods:
            return
        if not (status.startswith('200') or status.startswith('203')):
            return
        if environ['wsgi.url_scheme'] == 'https':
            if not self.store_https_responses:
                return
        if self._check_no_cache(response_headers, environ):
            return
        cc_header = header_value(response_headers, 'Cache-Control')
        if cc_header:
            cc_parts = parse_cache_control_header(cc_header)
            try:
                if int(cc_parts.get('max-age', '0')) == 0:
                    return
            except ValueError:
                return

        # if we didn't abort due to any condition above, store the response
        vary_header_names = []
        vary = header_value(response_headers, 'Vary')
        if vary is not None:
            vary_header_names.extend(
                [ x.strip().lower() for x in vary.split(',') ])
        if self.always_vary_on_headers:
            vary_header_names.extend(list(self.always_vary_on_headers))

        if '*' in vary_header_names:
            return

        discriminators = []
        for header_name in vary_header_names:
            value = header_value(request_headers, header_name)
            if value is not None:
                discriminators.append(('vary', (header_name, value)))
        for varname in self.always_vary_on_environ:
            value = environ.get(varname)
            if value is not None:
                discriminators.append(('env', (varname, value)))

        discriminators = tuple(sorted(discriminators))
        headers = endtoend(response_headers)
        url = construct_url(environ)

        # Response headers won't have a date if we aren't proxying to
        # another http server on our right hand side.
        date = header_value(response_headers, 'Date')
        if date is None:
            date = time.time()
        else:
            date = calendar.timegm(parsedate_tz(date))

        expires = self._expires(date, response_headers)

        # XXX purge?

        return self.storage.store(
            url,
            discriminators,
            expires,
            status,
            headers,
            )

    def _discriminate(self, entries, request_headers, environ):

        matching_entries = entries[:]

        for entry in entries:
            discrims, expires, status, headers, body, extras = entry
            for discrim in discrims:
                typ, (stored_name, stored_value) = discrim
                if typ == 'env':
                    strval = environ.get(stored_name)
                elif typ == 'vary':
                    strval = header_value(request_headers, stored_name)
                else: #pragma NO COVER
                    raise ValueError(discrim)
                if strval is None or strval != stored_value:
                    matching_entries.remove(entry)
                    break

        if matching_entries:
            match = matching_entries[0] # this is essentially random
            return match

    def _check_no_cache(self, headers, environ):
        for nocache in ('Pragma', 'Cache-Control'):
            value = header_value(headers, nocache)
            if value and 'no-cache' in value.lower():
                return True
        return False

    def _expires(self, date, headers):
        cc_header = header_value(headers, 'Cache-Control')
        expires_header = header_value(headers, 'Expires')

        # logic stolen from httplib2
        if cc_header is not None:
            header_parts = parse_cache_control_header(cc_header)
            if 'max-age' in header_parts:
                try:
                    lifetime = int(header_parts['max-age'])
                    return date + lifetime
                except ValueError: #pragma NO COVER belt-and-suspenders
                    return date

        if expires_header is not None:
            expires = parsedate_tz(expires_header)
            if expires is None:
                return date
            else:
                return calendar.timegm(expires)


def make_accelerator_policy(logger, storage, config):
    allowed_methods = config.get('policy.allowed_methods', 'GET')
    allowed_methods = [x.upper() for x in
                       filter(None, allowed_methods.split()) ]
    honor_shift_reload = config.get('policy.honor_shift_reload', False)
    honor_shift_reload = asbool(honor_shift_reload)
    store_https_responses = config.get('policy.store_https_responses',False)
    store_https_responses = asbool(store_https_responses)
    always_vary_on_headers = config.get('policy.always_vary_on_headers', '')
    always_vary_on_headers = filter(None, always_vary_on_headers.split())
    always_vary_on_environ = config.get('policy.always_vary_on_environ',
                                        'REQUEST_METHOD')
    always_vary_on_environ = filter(None, always_vary_on_environ.split())
    return AcceleratorPolicy(
        logger,
        storage,
        allowed_methods,
        always_vary_on_headers,
        always_vary_on_environ,
        honor_shift_reload,
        store_https_responses,
        )
directlyProvides(make_accelerator_policy, IPolicyFactory)

HOP_BY_HOP = ['connection',
              'keep-alive',
              'proxy-authenticate',
              'proxy-authorization',
              'te',
              'trailers',
              'transfer-encoding',
              'upgrade']

def endtoend(headers):
    connection_header = header_value(headers, 'Connection') or ''
    hop_by_hop = [x.strip().lower() for x in connection_header.split(',')]
    hop_by_hop.extend(HOP_BY_HOP)
    header_names = [ header[0] for header in headers ]
    return [(name, header_value(headers, name)) for name
             in header_names if name.lower() not in hop_by_hop]

def parse_cache_control_header(header):
    cc_parts = {}
    if header is not None:
        parts = [ x.strip() for x in header.split(',') ]
        for part in parts:
            if '=' in part:
                key, val = [ x.strip() for x in part.split('=', 1) ]
                cc_parts[key] = val
            else:
                cc_parts[part] = None
    return cc_parts

def asbool(val):
    val= str(val)
    if val.lower() in ('y', 'yes', 'true', 't'):
        return True
    return False

