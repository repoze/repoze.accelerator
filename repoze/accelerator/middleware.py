import itertools

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

def main(app, global_conf, **local_conf):
    from repoze.accelerator.storage import make_memory_storage
    from repoze.accelerator.policy import make_accelerator_policy

    storage_factory = local_conf.get('storage', make_memory_storage)
    storage = storage_factory(config=local_conf)

    policy_factory = local_conf.get('policy', make_accelerator_policy)
    policy = policy_factory(storage, config=local_conf)

    return Accelerator(app, policy)

