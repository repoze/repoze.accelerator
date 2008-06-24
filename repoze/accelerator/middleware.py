import itertools

class Accelerator:
    def __init__(self, app, policy, logger):
        self.app = app
        self.policy = policy
        self.logger = logger

    def __call__(self, environ, start_response):
        logger = self.logger

        result = self.policy.fetch(environ)

        if result is not None:
            logger and logger.info(
                'repoze.accelerator: HIT %s' % environ['PATH_INFO'])
            status, headers, content = result
            headers = list(headers) + [('X-Cached-By', 'repoze.accelerator')]
            start_response(status, headers)
            for chunk in content:
                yield chunk
            raise StopIteration

        logger and logger.info(
            'repoze.accelerator: MISS %s' % environ['PATH_INFO'])
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

def _resolveEntryPoint(name):
    from pkg_resources import EntryPoint
    return EntryPoint.parse('x=%s' % name).load(False)

def main(app, global_conf, **local_conf):
    from repoze.accelerator.storage import make_memory_storage
    from repoze.accelerator.policy import make_accelerator_policy
    from repoze.accelerator.logger import make_logger

    logger_factory = local_conf.get('logger', make_logger)
    if isinstance(logger_factory, basestring):
        logger_factory = _resolveEntryPoint(logger_factory)
    logger = logger_factory(local_conf)

    storage_factory = local_conf.get('storage', make_memory_storage)
    if isinstance(storage_factory, basestring):
        storage_factory = _resolveEntryPoint(storage_factory)
    storage = storage_factory(logger, local_conf)

    policy_factory = local_conf.get('policy', make_accelerator_policy)
    if isinstance(policy_factory, basestring):
        policy_factory = _resolveEntryPoint(policy_factory)
    policy = policy_factory(logger, storage, local_conf)

    return Accelerator(app, policy, logger)

