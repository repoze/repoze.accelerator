import unittest

class TestLoggerFactory(unittest.TestCase):
    def _getFUT(self):
        from repoze.accelerator.logger import make_logger
        return make_logger

    def test_factory_provides_ILoggerFactory(self):
        from zope.interface.verify import verifyObject
        from repoze.accelerator.interfaces import ILoggerFactory
        f = self._getFUT()
        verifyObject(ILoggerFactory, f)

    def test_default_config(self):
        f = self._getFUT()
        result = f({})
        self.assertEqual(result, None)

    def test_with_envvar(self):
        import os
        import logging
        import sys
        envvar = 'ACCELERATOR_LOG'
        try:
            os.environ[envvar] = '1'
            f = self._getFUT()
            logger = f({})
            self.failUnless(isinstance(logger, logging.Logger))
            self.assertEqual(logger.handlers[0].stream, sys.stdout)
        finally:
            del os.environ[envvar]
            
    def test_with_stdout_filename(self):
        import logging
        import sys
        f = self._getFUT()
        config = {'logger.filename':'stdout'}
        logger = f(config)
        self.failUnless(isinstance(logger, logging.Logger))
        self.assertEqual(logger.handlers[0].stream, sys.stdout)
        
    def test_with_stderr_filename(self):
        import logging
        import sys
        f = self._getFUT()
        config = {'logger.filename':'stderr'}
        logger = f(config)
        self.failUnless(isinstance(logger, logging.Logger))
        self.assertEqual(logger.handlers[0].stream, sys.stderr)

    def test_with_stderr_filename(self):
        import logging
        import sys
        f = self._getFUT()
        config = {'logger.filename':'stderr'}
        logger = f(config)
        self.failUnless(isinstance(logger, logging.Logger))
        self.assertEqual(logger.handlers[0].stream, sys.stderr)

    def test_with_real_filename(self):
        import os
        import tempfile
        tfn = tempfile.mktemp()
        try:
            import logging
            f = self._getFUT()
            config = {'logger.filename':tfn}
            logger = f(config)
            self.failUnless(isinstance(logger, logging.Logger))
            self.failUnless(isinstance(logger.handlers[0].stream, file))
        finally:
            os.remove(tfn)

    def test_override_level(self):
        import logging
        f = self._getFUT()
        config = {'logger.filename':'stderr',
                  'logger.log_level':'DEBUG'}
        logger = f(config)
        self.failUnless(isinstance(logger, logging.Logger))
        self.assertEqual(logger.level, logging.DEBUG)
