import unittest

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
        from repoze.accelerator.policy import AcceleratorPolicy
        from repoze.accelerator.storage import MemoryStorage
        app = self._makeApp()

        accel = self._callFUT(app, {})

        self.failUnless(accel.app is app)
        self.failUnless(isinstance(accel.policy, AcceleratorPolicy))
        self.failUnless(isinstance(accel.policy.storage, MemoryStorage))

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

        accel = self._callFUT(
            app,
            {},
            storage='repoze.accelerator.tests.test_middleware:_makeStorage',
            policy='repoze.accelerator.tests.test_middleware:_makePolicy',
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

