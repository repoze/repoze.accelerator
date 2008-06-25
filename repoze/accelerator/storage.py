import threading

from zope.interface import implements
from zope.interface import directlyProvides

from repoze.accelerator.interfaces import IChunkHandler
from repoze.accelerator.interfaces import IStorage
from repoze.accelerator.interfaces import IStorageFactory

class MemoryStorage:
    implements(IStorage)

    def __init__(self, logger, lock=threading.Lock()):
        self.logger = logger
        self.data = {}
        self.lock = lock

    def store(self, url, discriminators, expires, status, headers, **extras):
        body = []
        storage = self

        class SimpleHandler:
            implements(IChunkHandler)
            def write(self, chunk):
                body.append(chunk)

            def close(self):
                storage.lock.acquire()
                try:
                    entries = storage.data.setdefault(url, {})
                    entries[discriminators] = expires,status,headers,body,extras
                finally:
                    storage.lock.release()

        return SimpleHandler()
                
    def fetch(self, url):
        entries = self.data.get(url)
        if entries is None:
            return None
        L = []
        for discrims, (expires,status,headers,body,extras) in entries.items():
            L.append((discrims, expires, status, headers, body, extras))
        return L

def make_memory_storage(logger, config):
    return MemoryStorage(logger)
directlyProvides(make_memory_storage, IStorageFactory)
    
