import unittest

class TestAcceleratorPolicy(unittest.TestCase):
    def _getTargetClass(self):
        from repoze.accelerator.policy import AcceleratorPolicy
        return AcceleratorPolicy

    def _makeOne(self, storage):
        klass = self._getTargetClass()
        logger = None
        return klass(logger, storage)

    def _makeEnviron(self):
        return {
            'wsgi.url_scheme':'http',
            'SERVER_NAME':'example.com',
            'SERVER_PORT':'80',
            'REQUEST_METHOD': 'GET',
            }

    def _makeHeaders(self):
        from email.Utils import formatdate
        now = formatdate()
        return [('Date', now)]

    def test_class_conforms_to_IPolicy(self):
        from zope.interface.verify import verifyClass
        from repoze.accelerator.interfaces import IPolicy
        verifyClass(IPolicy, self._getTargetClass())

    def test_instance_conforms_to_IPolicy(self):
        from zope.interface.verify import verifyObject
        from repoze.accelerator.interfaces import IPolicy
        verifyObject(IPolicy, self._makeOne(DummyStorage()))

    def test_factory_provides_IPolicyFactory(self):
        from zope.interface.verify import verifyObject
        from repoze.accelerator.interfaces import IPolicyFactory
        from repoze.accelerator.policy import make_accelerator_policy
        verifyObject(IPolicyFactory, make_accelerator_policy)

    def test_store_not_cacheable_post_request_method(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['REQUEST_METHOD'] = 'POST'
        headers = self._makeHeaders()
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

    def test_store_not_cacheable_pragma_no_cache(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        headers.append(('pragma', 'no-cache'))
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

    def test_store_not_cacheable_cachecontrol_no_cache(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        headers.append(('cache-control', 'no-cache'))
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

    def test_store_not_cacheable_non_2XX_response(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        result = policy.store('500 Error', headers, environ)
        self.assertEqual(result, None)

    def test_store_not_cacheable_cc_maxage_zero(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        headers.append(('Cache-Control', 'max-age=0'))
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

    def test_store_not_cacheable_bad_maxage(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        headers.append(('Cache-Control', 'max-age=thisisbad'))
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

    def test_store_not_cacheable_maxage_None(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        headers.append(('Cache-Control', 'public'))
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

    def test_store_not_cacheable_nostore_https_responses(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        policy.store_https_responses = False
        environ = self._makeEnviron()
        environ['wsgi.url_scheme'] = 'https'
        headers = self._makeHeaders()
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

    def test_store_no_date_header_stores_today(self):
        storage = DummyStorage(store_result=True)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = [('Cache-Control', 'max-age=400')]
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, True)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.headers, headers)
        self.failIf(storage.expires is None)

    def test_store_with_date_header_stores_then(self):
        storage = DummyStorage(store_result=True)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        from email.Utils import formatdate
        then = formatdate(0)
        headers = [('Cache-Control', 'max-age=400'), ('Date', then)]
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, True)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.headers, headers)
        self.assertEqual(storage.expires, 400)

    def test_store_allowed_request_method_cacheable(self):
        storage = DummyStorage(store_result=True)
        policy = self._makeOne(storage)
        policy.allowed_methods = ('FOO',)
        environ = self._makeEnviron()
        environ['REQUEST_METHOD'] = 'FOO'
        headers = self._makeHeaders()
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, True)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.headers, headers)

    def test_store_no_request_method_cacheable(self):
        storage = DummyStorage(store_result=True)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        del environ['REQUEST_METHOD']
        headers = self._makeHeaders()
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, True)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.headers, headers)

    def test_store_get_request_method_cacheable(self):
        storage = DummyStorage(store_result=True)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, True)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.headers, headers)

    def test_store_with_request_vary(self):
        storage = DummyStorage(store_result=True)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        headers.append(('Vary', 'Cookie'))
        environ['HTTP_COOKIE'] = '12345'
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, True)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.headers, headers)
        discrims = storage.discrims
        self.assertEqual(len(discrims), 2)
        self.assertEqual(discrims[0], ('env', ('REQUEST_METHOD', 'GET')))
        self.assertEqual(discrims[1], ('vary', ('cookie', '12345')))

    def test_store_with_always_request_vary(self):
        storage = DummyStorage(store_result=True)
        policy = self._makeOne(storage)
        policy.always_vary_on_headers = ('cookie',)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        environ['HTTP_COOKIE'] = '12345'
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, True)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.headers, headers)
        discrims = storage.discrims
        self.assertEqual(len(discrims), 2)
        self.assertEqual(discrims[0], ('env', ('REQUEST_METHOD', 'GET')))
        self.assertEqual(discrims[1], ('vary', ('cookie', '12345')))

    def test_store_with_always_request_vary_and_plain_request_vary(self):
        storage = DummyStorage(store_result=True)
        policy = self._makeOne(storage)
        policy.always_vary_on_headers = ('cookie',)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        headers.append(('Vary', 'X-Foo'))
        environ['HTTP_COOKIE'] = '12345'
        environ['HTTP_X_FOO'] = 'xfoo'
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, True)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.headers, headers)
        discrims = storage.discrims
        self.assertEqual(len(discrims), 3)
        self.assertEqual(discrims[0], ('env', ('REQUEST_METHOD', 'GET')))
        self.assertEqual(discrims[1], ('vary', ('cookie', '12345')))
        self.assertEqual(discrims[2], ('vary', ('x-foo', 'xfoo')))

    def test_store_with_always_request_vary_star(self):
        storage = DummyStorage(store_result=True)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        headers.append(('Vary', '*'))
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

    def test_store_with_environ_vary(self):
        storage = DummyStorage(store_result=True)
        policy = self._makeOne(storage)
        policy.always_vary_on_environ = ('REMOTE_USER',)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        environ['REMOTE_USER'] = '12345'
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, True)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.headers, headers)
        discrims = storage.discrims
        self.assertEqual(len(discrims), 1)
        self.assertEqual(discrims[0], ('env', ('REMOTE_USER', '12345')))

    def test_store_with_environ_vary_and_req_vary(self):
        storage = DummyStorage(store_result=True)
        policy = self._makeOne(storage)
        policy.always_vary_on_environ = ('REMOTE_USER',)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        headers.append(('Vary', 'Cookie'))
        environ['REMOTE_USER'] = '12345'
        environ['HTTP_COOKIE'] = '12345'
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, True)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.headers, headers)
        discrims = storage.discrims
        self.assertEqual(len(discrims), 2)
        self.assertEqual(discrims[0], ('env', ('REMOTE_USER', '12345')))
        self.assertEqual(discrims[1], ('vary', ('cookie', '12345')))

    def test_fetch_fails_post_request_method(self):
        storage = DummyStorage(fetch_result=False)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['REQUEST_METHOD'] = 'POST'
        result = policy.fetch(environ)
        self.failIfEqual(result, False)

    def test_fetch_fails_pragma_no_cache(self):
        storage = DummyStorage(fetch_result=False)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['HTTP_PRAGMA'] = 'no-cache'
        result = policy.fetch(environ)
        self.failIfEqual(result, False)

    def test_fetch_fails_cachecontrol_no_cache(self):
        storage = DummyStorage(fetch_result=False)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['HTTP_PRAGMA'] = 'no-cache'
        result = policy.fetch(environ)
        self.failIfEqual(result, False)

    def test_fetch_fails_range_request(self):
        storage = DummyStorage(fetch_result=False)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['HTTP_RANGE'] = '200-300'
        result = policy.fetch(environ)
        self.failIfEqual(result, False)

    def test_fetch_fails_conditional_ims_request(self):
        storage = DummyStorage(fetch_result=False)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['HTTP_IF_MODIFIED_SINCE'] = 'whenever'
        result = policy.fetch(environ)
        self.failIfEqual(result, False)

    def test_fetch_fails_conditional_if_none_match_request(self):
        storage = DummyStorage(fetch_result=False)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['HTTP_IF_NONE_MATCH'] = 'yeah'
        result = policy.fetch(environ)
        self.failIfEqual(result, False)

    def test_fetch_fails_conditional_if_match_request(self):
        storage = DummyStorage(fetch_result=False)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['HTTP_IF_MATCH'] = 'yeah'
        result = policy.fetch(environ)
        self.failIfEqual(result, False)

    def test_fetch_succeeds_no_request_method(self):
        headers = self._makeHeaders()
        cc = 'max-age=4000'
        headers.append(('Cache-Control', cc))
        import sys
        expected = ([], sys.maxint, 200, headers, [], {})
        storage = DummyStorage(fetch_result=[expected])
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        del environ['REQUEST_METHOD']
        result = policy.fetch(environ)
        self.assertEqual(result, expected[2:-1])

    def test_fetch_succeeds_get_request_method(self):
        headers = self._makeHeaders()
        cc = 'max-age=4000'
        headers.append(('Cache-Control', cc))
        import sys
        expected = ([], sys.maxint, 200, headers, [], {})
        storage = DummyStorage(fetch_result=[expected])
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        result = policy.fetch(environ)
        self.assertEqual(result, expected[2:-1])

    def test_fetch_succeeds_more_than_one_response_from_storage(self):
        headers = self._makeHeaders()
        cc = 'max-age=4000'
        headers.append(('Cache-Control', cc))
        import sys
        expected1 = ([], sys.maxint, 200, headers, [], {})
        expected2 = ([], sys.maxint, 200, headers, [], {})
        storage = DummyStorage(fetch_result=[expected1] + [expected2])
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        result = policy.fetch(environ)
        self.assertEqual(result, expected1[2:-1])

    def test_fetch_succeeds_via_discrimination(self):
        headers = self._makeHeaders()
        cc = 'max-age=4000'
        headers.append(('Cache-Control', cc))
        import sys
        then = sys.maxint
        stored = [
            ([('vary', ('Cookie', '12345'))], then, 200, headers, [], {}),
            ([('vary', ('Cookie', '12345')), ('vary', ('X-Foo', '12345'))],
             then, 200, headers, [], {}),
            ([('vary', ('X-Bar', '123'))], then, 200, headers, [], {}),
            ]
        storage = DummyStorage(fetch_result=stored)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['HTTP_COOKIE'] = '12345'
        environ['HTTP_X_FOO'] = '12345'
        result = policy.fetch(environ)
        self.assertEqual(result, stored[0][2:-1])

    def test_fetch_fails_via_discrimination(self):
        headers = self._makeHeaders()
        cc = 'max-age=4000'
        headers.append(('Cache-Control', cc))
        stored = [
            ([('vary', ('Cookie', '12345'))], 0, 200, headers, [], {}),
            ([('vary', ('Cookie', '12345')), ('vary', ('X-Foo', '12345'))],
                  0, 200, headers, [], {}),
            ([('vary', ('X-Bar', '123'))], 0, 200, headers, [], {}),
            ]
        storage = DummyStorage(fetch_result=stored)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['HTTP_COOKIE'] = '5678'
        environ['HTTP_X_FOO'] = '5678'
        result = policy.fetch(environ)
        self.assertEqual(result, None)

    def test_fetch_fails_no_response_from_storage(self):
        headers = self._makeHeaders()
        cc = 'max-age=4000'
        headers.append(('Cache-Control', cc))
        storage = DummyStorage(fetch_result=[])
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        result = policy.fetch(environ)
        self.assertEqual(result, None)

    def test_fresh_via_max_age(self):
        headers = self._makeHeaders()
        headers.append(('Cache-Control', 'max-age=4000'))
        import sys
        expected = ([], sys.maxint, 200, headers, [], {})
        storage = DummyStorage(fetch_result=[expected])
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        result = policy.fetch(environ)
        self.assertEqual(result, (200, headers, []))

    def test_fresh_via_expires(self):
        headers = self._makeHeaders()
        from email.Utils import formatdate
        import time
        expires = formatdate(time.time() + 5000)
        headers.append(('Expires', expires))
        import sys
        expected = ([], sys.maxint, 200, headers, [], {})
        storage = DummyStorage(fetch_result=[expected])
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        result = policy.fetch(environ)
        self.assertEqual(result, (200, headers, []))

    def test_stale_via_max_age(self):
        import time
        from email.Utils import formatdate
        date = formatdate(time.time() - 5000)
        headers = [('Date', date)]
        headers.append(('Cache-Control', 'max-age=10'))
        expected = ([], 0, 200, headers, [], {})
        storage = DummyStorage(fetch_result=[expected])
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        result = policy.fetch(environ)
        self.assertEqual(result, None)

    def test_stale_via_expires(self):
        headers = self._makeHeaders()
        import time
        from email.Utils import formatdate
        expires = formatdate(time.time() - 5000)
        headers.append(('Expires', expires))
        expected = ([], 0, 200, headers, [], {})
        storage = DummyStorage(fetch_result=[expected])
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        result = policy.fetch(environ)
        self.assertEqual(result, None)

    def test_make_accelerator_policy_factory_defaults(self):
        from repoze.accelerator.policy import make_accelerator_policy
        policy = make_accelerator_policy(None, DummyStorage(), {})
        self.assertEqual(policy.allowed_methods, ['GET'])
        self.assertEqual(policy.honor_shift_reload, False)
        self.assertEqual(policy.store_https_responses, False)
        self.assertEqual(policy.always_vary_on_headers, [])
        self.assertEqual(policy.always_vary_on_environ, ['REQUEST_METHOD'])
        self.assertEqual(policy.logger, None)

    def test_make_accelerator_policy_factory_overrides(self):
        from repoze.accelerator.policy import make_accelerator_policy
        config = {'policy.allowed_methods':'POST GET',
                  'policy.honor_shift_reload':'true',
                  'policy.store_https_responses':'true',
                  'policy.always_vary_on_headers':'Cookie X-Foo',
                  'policy.always_vary_on_environ':'REMOTE_USER'}
        policy = make_accelerator_policy(None, DummyStorage(), config)
        self.assertEqual(policy.allowed_methods, ['POST', 'GET'])
        self.assertEqual(policy.honor_shift_reload, True)
        self.assertEqual(policy.store_https_responses, True)
        self.assertEqual(policy.always_vary_on_headers, ['Cookie', 'X-Foo'])
        self.assertEqual(policy.always_vary_on_environ, ['REMOTE_USER'])
        self.assertEqual(policy.logger, None)

class DummyStorage:
    def __init__(self, fetch_result=None, store_result=None):
        self.fetch_result = fetch_result
        self.store_result = store_result

    def store(self, url, discrims, expires, status, headers, **extras):
        self.url = url
        self.discrims = discrims
        self.expires = expires
        self.status = status
        self.headers = headers
        self.extras = extras
        return self.store_result

    def fetch(self, url):
        return self.fetch_result
