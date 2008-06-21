import itertools
import threading

from paste.request import construct_url
from paste.request import parse_headers
from paste.response import header_value

from repoze.accelerator.interfaces import IChunkHandler
from repoze.accelerator.interfaces import IPolicy
from repoze.accelerator.interfaces import IPolicyFactory
from repoze.accelerator.interfaces import IStorage
from repoze.accelerator.interfaces import IStorageFactory
from repoze.accelerator.interfaces import implements
from repoze.accelerator.interfaces import provides

class Accelerator:
    def __init__(self, app, policy):
        self.app = app
        self.policy = policy

    def __call__(self, environ, start_response):
        result = self.policy.fetch(environ)

        if result is not None:
            status, headers, content = result
            headers = list(headers) + [('X-Cached-By', 'repoze.accelerator')]
            start_response(status, headers)
            for chunk in content:
                yield chunk
            raise StopIteration

        catch_response = []
        written = []

        def replace_start_response(status, headers, exc_info=None):
            catch_response[:] = [status, headers, exc_info]
            return written.append

        app_iter = self.app(environ, replace_start_response)

        if catch_response:
            start_response(*catch_response)
            status, headers, exc_info = catch_response
        else:
            raise RuntimeError('start_response not called')

        handler = self.policy.store(status, headers, environ)

        chunks = itertools.chain(written, app_iter)

        for chunk in chunks:
            yield chunk
            if handler is not None:
                handler.write(chunk)

        if handler is not None:
            handler.close()

        raise StopIteration



class NullPolicy:
    """ Pass-through, caches nothing.
    """
    implements(IPolicy)
    provides(IPolicyFactory)

    def __init__(self, storage, config=None):
        pass

    def fetch(self, environ):
        return None

    def store(self, status, headers, environ):
        pass

class NaivePolicy:
    implements(IPolicy)
    provides(IPolicyFactory)

    def __init__(self, storage, config=None):
        self.storage = storage
        if config is None:
            config = {}
        allowed_methods = config.get('policy.allowed_methods', 'GET')
        self.allowed_methods = filter(None, allowed_methods.split())

    def _minimalCacheOK(self, headers, environ):
        if environ.get('REQUEST_METHOD', 'GET') not in self.allowed_methods:
            return False
        for nocache in ('Pragma', 'Cache-Control'):
            value = header_value(headers, nocache)
            if value and 'no-cache' in value.lower():
                return False
        return True

    def store(self, status, headers, environ):
        if not self._minimalCacheOK(headers, environ):
            return

        if not status.startswith('200') or status.startswith('203'):
            return

        outheaders = []
        for key, val in headers:
            if key.lower() not in ('status', 'content-encoding',
                                   'transfer-encoding'):
                outheaders.append((key, val))

        url = construct_url(environ)

        return self.storage.store(url, status, outheaders)
    
    def fetch(self, environ):
        headers = parse_headers(environ)

        if not self._minimalCacheOK(headers, environ):
            return

        url = construct_url(environ)

        return self.storage.fetch(url)

class RAMStorage:
    implements(IStorage)
    provides(IStorageFactory)

    def __init__(self, lock=threading.Lock(), config=None):
        self.data = {}
        self.lock = lock

    def store(self, url, status, headers):
        result = []
        storage = self

        class SimpleHandler:
            implements(IChunkHandler)
            def write(self, chunk):
                result.append(chunk)

            def close(self):
                storage.lock.acquire()
                try:
                    storage.data[url] = (status, headers, result)
                finally:
                    storage.lock.release()

        return SimpleHandler()
                
    def fetch(self, url):
        return self.data.get(url)

def main(app, global_conf, **local_conf):

    storage_factory = local_conf.get('storage', RAMStorage)
    storage = storage_factory(config=local_conf)

    policy_factory = local_conf.get('policy', NaivePolicy)
    policy = policy_factory(storage, config=local_conf)

    return Accelerator(app, policy)

