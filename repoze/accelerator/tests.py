import unittest

class TestRAMStorage(unittest.TestCase):
    def _getTargetClass(self):
        from repoze.accelerator.middleware import RAMStorage
        return RAMStorage

    def _makeOne(self, lock):
        klass = self._getTargetClass()
        return klass(lock)
        
    def test_store_nonexistent(self):
        lock = DummyLock()
        storage = self._makeOne(lock)
        headers = [('Header1', 'value1')]
        handler = storage.store('url', 'status', headers)
        self.failIf(handler is None)
        chunks = ['chunk1', 'chunk2']
        for chunk in ('chunk1', 'chunk2'):
            handler.write(chunk)
        handler.close()
        self.assertEqual(storage.data['url'], ('status', headers, chunks))
        self.assertEqual(lock.acquired, 1)
        self.assertEqual(lock.released, 1)

    def test_store_existing(self):
        lock = DummyLock()
        storage = self._makeOne(lock)
        storage.data['url'] = ('otherstatus', (), ())
        headers = [('Header1', 'value1')]
        handler = storage.store('url', 'status', headers)
        self.failIf(handler is None)
        chunks = ['chunk1', 'chunk2']
        for chunk in ('chunk1', 'chunk2'):
            handler.write(chunk)
        handler.close()
        self.assertEqual(storage.data['url'], ('status', headers, chunks))
        self.assertEqual(lock.acquired, 1)
        self.assertEqual(lock.released, 1)

    def test_fetch_nonexistent(self):
        lock = DummyLock()
        storage = self._makeOne(lock)
        self.assertEqual(storage.fetch('url'), None)
        
    def test_fetch_existing(self):
        lock = DummyLock()
        storage = self._makeOne(lock)
        storage.data['url'] = 1
        self.assertEqual(storage.fetch('url'), 1)

class TestNaivePolicy(unittest.TestCase):
    def _getTargetClass(self):
        from repoze.accelerator.middleware import NaivePolicy
        return NaivePolicy

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

    def test_store_no_request_method_cacheable(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        del environ['REQUEST_METHOD']
        result = policy.store('200 OK', [('header1', 'value1')], environ)
        self.assertEqual(result, False)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.outheaders, [('header1', 'value1')])

    def test_store_get_request_method_cacheable(self):
        storage = DummyStorage()
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        result = policy.store('200 OK', [('header1', 'value1')], environ)
        self.assertEqual(result, False)
        self.assertEqual(storage.url, 'http://example.com')
        self.assertEqual(storage.status, '200 OK')
        self.assertEqual(storage.outheaders, [('header1', 'value1')])

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
        storage = DummyStorage(result=123)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        del environ['REQUEST_METHOD']
        result = policy.fetch(environ)
        self.assertEqual(result, 123)

    def test_fetch_succeeds_get_request_method(self):
        storage = DummyStorage(result=123)
        policy = self._makeOne(storage)
        environ = self._makeEnviron()
        result = policy.fetch(environ)
        self.assertEqual(result, 123)

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
    def __init__(self, result=None, writer=False):
        self.result = result
        self.writer = writer
        
    def store(self, url, status, outheaders):
        self.url = url
        self.status = status
        self.outheaders = outheaders
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
        
