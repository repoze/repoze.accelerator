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

    def store(self, url, status, headers, req_discrims, env_discrims):
        body = []
        storage = self
        req_discrims = tuple(req_discrims)
        env_discrims = tuple(env_discrims)

        class SimpleHandler:
            implements(IChunkHandler)
            def write(self, chunk):
                body.append(chunk)

            def close(self):
                storage.lock.acquire()
                try:
                    discrims = storage.data.setdefault(url, {})
                    discrims[(req_discrims, env_discrims)]=status, headers, body
                finally:
                    storage.lock.release()

        return SimpleHandler()
                
    def fetch(self, url):
        discrims = self.data.get(url)
        if discrims is None:
            return None
        L = []
        for (req_d, env_d), (status, headers, body) in discrims.items():
            L.append((status, headers, body, req_d, env_d))
        return L

def make_memory_storage(logger, config):
    return MemoryStorage(logger)
directlyProvides(make_memory_storage, IStorageFactory)
    
