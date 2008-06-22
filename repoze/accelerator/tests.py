import unittest

_MARKER = object()

class TestMemoryStorage(unittest.TestCase):
    def _getTargetClass(self):
        from repoze.accelerator.storage import MemoryStorage
        return MemoryStorage

    def _makeOne(self, lock):
        klass = self._getTargetClass()
        return klass(lock)

    def test_class_conforms_to_IStorage(self):
        from zope.interface.verify import verifyClass
        from repoze.accelerator.interfaces import IStorage
        verifyClass(IStorage, self._getTargetClass())

    def test_instance_conforms_to_IStorage(self):
        from zope.interface.verify import verifyObject
        from repoze.accelerator.interfaces import IStorage
        verifyObject(IStorage, self._makeOne(DummyLock()))

    def test_factory_provides_IStorageFactory(self):
        from zope.interface.verify import verifyObject
        from repoze.accelerator.interfaces import IStorageFactory
        from repoze.accelerator.storage import make_memory_storage
        verifyObject(IStorageFactory, make_memory_storage)

    def test_store_nonexistent(self):
        lock = DummyLock()
        storage = self._makeOne(lock)
        headers = [('Header1', 'value1')]
        handler = storage.store('url', 'status', headers, [], [])
        self.failIf(handler is None)
        chunks = ['chunk1', 'chunk2']
        for chunk in ('chunk1', 'chunk2'):
            handler.write(chunk)
        handler.close()
        self.assertEqual(storage.data['url'][(), ()],
                         ('status', headers, chunks))
        self.assertEqual(lock.acquired, 1)
        self.assertEqual(lock.released, 1)

    def test_store_existing(self):
        lock = DummyLock()
        storage = self._makeOne(lock)
        storage.data['url'] = {}
        storage.data['url'][(), ()] = ('otherstatus', (), ())
        headers = [('Header1', 'value1')]
        handler = storage.store('url', 'status', headers, [], [])
        self.failIf(handler is None)
        chunks = ['chunk1', 'chunk2']
        for chunk in ('chunk1', 'chunk2'):
            handler.write(chunk)
        handler.close()
        self.assertEqual(storage.data['url'][(), ()],
                         ('status', headers, chunks))
        self.assertEqual(lock.acquired, 1)
        self.assertEqual(lock.released, 1)

    def test_fetch_nonexistent(self):
        lock = DummyLock()
        storage = self._makeOne(lock)
        self.assertEqual(storage.fetch('url'), None)

    def test_fetch_existing(self):
        lock = DummyLock()
        storage = self._makeOne(lock)
        storage.data['url'] = {
            (1, 2):(200, [], []),
            (3, 4):(203, [], [])
            }
        result = storage.fetch('url')
        result.sort()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], (200, [], [], 1, 2))
        self.assertEqual(result[1], (203, [], [], 3, 4))


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
        result = policy.store('200 OK', [], environ)
        self.assertEqual(result, None)

    def test_store_not_cacheable_pragma_no_cache(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = [ ('pragma', 'no-cache') ]
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

    def test_store_not_cacheable_cachecontrol_no_cache(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = [ ('cache-control', 'no-cache') ]
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

    def test_store_not_cacheable_cachecontrol_no_cache(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        headers = [ ('cache-control', 'no-cache') ]
        result = policy.store('200 OK', headers, environ)
        self.assertEqual(result, None)

    def test_store_not_cacheable_non_2XX_response(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        result = policy.store('500 Error', [], environ)
        self.assertEqual(result, None)

    def test_store_allowed_request_method_cacheable(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        policy.allowed_methods = ('FOO',)
        environ = self._makeEnviron()
        environ['REQUEST_METHOD'] = 'FOO'
        from email.Utils import formatdate
        now = formatdate()
        result = policy.store('200 OK', [('Date', now)], environ)
        self.assertEqual(result, None)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.outheaders, [('Date', now)])

    def test_store_no_request_method_cacheable(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        del environ['REQUEST_METHOD']
        from email.Utils import formatdate
        now = formatdate()
        result = policy.store('200 OK', [('Date', now)], environ)
        self.assertEqual(result, None)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.outheaders, [('Date', now)])

    def test_store_get_request_method_cacheable(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        from email.Utils import formatdate
        now = formatdate()
        result = policy.store('200 OK', [('Date', now)], environ)
        self.assertEqual(result, None)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.outheaders, [('Date', now)])

    def test_fetch_fails_post_request_method(self):
        storage = DummyStorage(result=123)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['REQUEST_METHOD'] = 'POST'
        result = policy.fetch(environ)
        self.failIfEqual(result, 123)

    def test_fetch_fails_pragma_no_cache(self):
        storage = DummyStorage(result=123)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['HTTP_PRAGMA'] = 'no-cache'
        result = policy.fetch(environ)
        self.failIfEqual(result, 123)

    def test_fetch_fails_cachecontrol_no_cache(self):
        storage = DummyStorage(result=123)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        environ['HTTP_PRAGMA'] = 'no-cache'
        result = policy.fetch(environ)
        self.failIfEqual(result, 123)

    def test_fetch_succeeds_no_request_method(self):
        from email.Utils import formatdate
        now = formatdate()
        cc = 'max-age=4000'
        expected = (200, [('Date', now), ('Cache-Control', cc)], [], [], [])
        storage = DummyStorage(result=[expected])
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        del environ['REQUEST_METHOD']
        result = policy.fetch(environ)
        self.assertEqual(result, expected[:3])

    def test_fetch_succeeds_get_request_method(self):
        from email.Utils import formatdate
        now = formatdate()
        cc = 'max-age=4000'
        expected = (200, [('Date', now), ('Cache-Control', cc)], [], [], [])
        storage = DummyStorage(result=[expected])
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        result = policy.fetch(environ)
        self.assertEqual(result, expected[:3])

class TestAcceleratorMiddleware(unittest.TestCase):
    def _getTargetClass(self):
        from repoze.accelerator.middleware import Accelerator
        return Accelerator

    def _makeOne(self, app, policy):
        klass = self._getTargetClass()
        return klass(app, policy)

    def _makeEnviron(self):
        return {}

    def test_call_fetch_from_cache(self):
        app = DummyApp()
        policy = DummyPolicy(result=('200 OK', [], ['abc', 'def']))
        environ = self._makeEnviron()
        accelerator = self._makeOne(app, policy)
        start_response = DummyStartResponse()
        generator = accelerator(environ, start_response)
        self.assertEqual(list(generator), ['abc', 'def'])
        self.assertEqual(start_response.status, '200 OK')
        self.assertEqual(start_response.headers,
                         [('X-Cached-By', 'repoze.accelerator')])
        self.assertEqual(start_response.exc_info, None)

    def test_call_nofetch_start_response_not_called(self):
        app = DummyApp()
        app.call_start_response = False
        policy = DummyPolicy(result=None)
        environ = self._makeEnviron()
        accelerator = self._makeOne(app, policy)
        start_response = DummyStartResponse()
        result = accelerator(environ, start_response)
        self.assertRaises(RuntimeError, list, result)

    def test_call_cantstore(self):
        app = DummyApp(headers=[('a', 'b')])
        policy = DummyPolicy(result=None)
        policy.handler = None
        environ = self._makeEnviron()
        accelerator = self._makeOne(app, policy)
        start_response = DummyStartResponse()
        result = list(accelerator(environ, start_response))
        self.assertEqual(result, ['hello', 'world'])
        self.assertEqual(start_response.status, '200 OK')
        self.assertEqual(start_response.headers, [('a', 'b')])
        self.assertEqual(start_response.exc_info, None)

    def test_call_canstore(self):
        app = DummyApp(headers=[('a', 'b')])
        policy = DummyPolicy(result=None)
        policy.handler = DummyHandler()
        environ = self._makeEnviron()
        accelerator = self._makeOne(app, policy)
        start_response = DummyStartResponse()
        result = list(accelerator(environ, start_response))
        self.assertEqual(result, ['hello', 'world'])
        self.assertEqual(start_response.status, '200 OK')
        self.assertEqual(start_response.headers, [('a', 'b')])
        self.assertEqual(start_response.exc_info, None)
        self.assertEqual(policy.handler.chunks, ['hello', 'world'])
        self.assertEqual(policy.handler.closed, True)


class Test_main(unittest.TestCase):

    def _callFUT(self, app, global_conf, **local_conf):
        from repoze.accelerator.middleware import main
        return main(app, global_conf, **local_conf)

    def _makeApp(self):
        return object()

    def test_main_defaults(self):
        from repoze.accelerator.middleware import NaivePolicy
        from repoze.accelerator.middleware import RAMStorage
        app = self._makeApp()

        accel = self._callFUT(app, {})

        self.failUnless(accel.app is app)
        self.failUnless(isinstance(accel.policy, NaivePolicy))
        self.failUnless(isinstance(accel.policy.storage, RAMStorage))

    def test_main_factories(self):

        app = self._makeApp()

        accel = self._callFUT(app,
                              {},
                              storage=_makeStorage,
                              policy=_makePolicy,
                             )

        self.failUnless(accel.app is app)
        self.failUnless(isinstance(accel.policy, _Policy))
        self.failUnless(isinstance(accel.policy.config, dict))
        self.failUnless(isinstance(accel.policy.storage.config, dict))

    def test_main_entry_points(self):

        app = self._makeApp()

        accel = self._callFUT(app,
                              {},
                              storage='repoze.accelerator.tests:_makeStorage',
                              policy='repoze.accelerator.tests:_makePolicy',
                             )

        self.failUnless(accel.app is app)
        self.failUnless(isinstance(accel.policy, _Policy))
        self.failUnless(isinstance(accel.policy.config, dict))
        self.failUnless(isinstance(accel.policy.storage.config, dict))

class _Storage:
    config = None

def _makeStorage(config=None):
    storage = _Storage()
    if config is not None:
        storage.config = config
    return storage

class _Policy:
    config = None

    def __init__(self, storage):
        self.storage = storage

def _makePolicy(storage, config=None):
    policy = _Policy(storage)
    if config is not None:
        policy.config = config
    return policy

class DummyHandler:
    def __init__(self):
        self.chunks = []
        self.closed = False
    def write(self, chunk):
        self.chunks.append(chunk)
    def close(self):
        self.closed = True

class DummyStartResponse:
    def __call__(self, status, headers, exc_info=None):
        self.status = status
        self.headers = headers
        self.exc_info = exc_info

class DummyApp:
    def __init__(self, status='200 OK', headers=()):
        self.status = status
        self.headers = headers
        self.call_start_response = True

    def __call__(self, environ, start_response):
        self.environ = environ
        if self.call_start_response:
            start_response(self.status, self.headers)
        return ['hello', 'world']

class DummyPolicy:
    def __init__(self, result):
        self.result = result
        self.handler = None

    def fetch(self, environ):
        return self.result

    def store(self, status, headers, environ):
        return self.handler

class DummyStorage:
    def __init__(self, result=None, writer=None):
        self.result = result
        self.writer = writer

    def store(self, url, status, outheaders, req_discrims, env_discrims):
        self.url = url
        self.status = status
        self.outheaders = outheaders
        self.req_discrims = req_discrims
        self.env_discrims = env_discrims
        return self.writer

    def fetch(self, url):
        return self.result

class DummyLock:
    def __init__(self):
        self.acquired = 0
        self.released = 0

    def acquire(self):
        self.acquired += 1

    def release(self):
        self.released += 1

