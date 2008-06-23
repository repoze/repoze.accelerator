import unittest

class TestAcceleratorPolicy(unittest.TestCase):
    def _getTargetClass(self):
        from repoze.accelerator.policy import AcceleratorPolicy
        return AcceleratorPolicy

    def _makeOne(self, storage):
        klass = self._getTargetClass()
        return klass(storage)

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

    def test_store_not_cacheable_nostore_https_responses(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        policy.store_https_responses = False
        environ = self._makeEnviron()
        environ['wsgi.url_scheme'] = 'https'
        headers = self._makeHeaders()
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

    def test_store_not_cacheable_no_date_header(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = [('Cache-Control', 'max-age=400')]
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

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
        self.assertEqual(storage.outheaders, headers)

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
        self.assertEqual(storage.outheaders, headers)

    def test_store_get_request_method_cacheable(self):
        storage = DummyStorage(store_result=True)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = self._makeHeaders()
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, True)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.outheaders, headers)

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
        self.assertEqual(storage.outheaders, headers)
        self.assertEqual(storage.req_discrims, [('cookie', '12345')])

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
        self.assertEqual(storage.outheaders, headers)
        self.assertEqual(storage.req_discrims, [('cookie', '12345')])

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
        self.assertEqual(storage.outheaders, headers)
        self.assertEqual(storage.req_discrims,
                         [('cookie', '12345'), ('x-foo', 'xfoo')])

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
        self.assertEqual(storage.outheaders, headers)
        self.assertEqual(storage.env_discrims, [('REMOTE_USER', '12345')])

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
        self.assertEqual(storage.outheaders, headers)
        self.assertEqual(storage.req_discrims, [('cookie', '12345')])
        self.assertEqual(storage.env_discrims, [('REMOTE_USER', '12345')])

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

    def test_fetch_succeeds_no_request_method(self):
        headers = self._makeHeaders()
        cc = 'max-age=4000'
        headers.append(('Cache-Control', cc))
        expected = (200, headers, [], [], [])
        storage = DummyStorage(fetch_result=[expected])
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        del environ['REQUEST_METHOD']
        result = policy.fetch(environ)
        self.assertEqual(result, expected[:3])

    def test_fetch_succeeds_get_request_method(self):
        headers = self._makeHeaders()
        cc = 'max-age=4000'
        headers.append(('Cache-Control', cc))
        expected = (200, headers, [], [], [])
        storage = DummyStorage(fetch_result=[expected])
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        result = policy.fetch(environ)
        self.assertEqual(result, expected[:3])

class DummyStorage:
    def __init__(self, fetch_result=None, store_result=None):
        self.fetch_result = fetch_result
        self.store_result = store_result

    def store(self, url, status, outheaders, req_discrims, env_discrims):
        self.url = url
        self.status = status
        self.outheaders = outheaders
        self.req_discrims = req_discrims
        self.env_discrims = env_discrims
        return self.store_result

    def fetch(self, url):
        return self.fetch_result
