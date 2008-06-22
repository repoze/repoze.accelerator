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

class DummyLock:
    def __init__(self):
        self.acquired = 0
        self.released = 0

    def acquire(self):
        self.acquired += 1

    def release(self):
        self.released += 1

