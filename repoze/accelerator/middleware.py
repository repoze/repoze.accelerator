import itertools
import threading

from paste.request import construct_url
from paste.request import parse_headers
from paste.response import header_value

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
    def fetch(self, environ):
        return None
    def store(self, status, headers, environ):
        pass

class NaivePolicy:
    def __init__(self, storage):
        self.storage = storage

    def _minimalCacheOK(self, headers, environ):
        if environ.get('REQUEST_METHOD', 'GET') != 'GET':
            return False
        for nocache in ('Pragma', 'Cache-Control'):
            value = header_value(headers, nocache)
            if value and 'no-cache' in value.lower():
                return
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
    def __init__(self, lock=threading.Lock()):
        self.data = {}
        self.lock = lock

    def store(self, url, status, headers):
        result = []
        storage = self

        class SimpleHandler:
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
    storage = RAMStorage()
    policy = NaivePolicy(storage)
    return Accelerator(app, policy)

