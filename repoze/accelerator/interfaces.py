from zope.interface import Interface

class IChunkHandler(Interface):
    """ API of the helper object returned from a call to 'IStorage.store'.
    """
    def write(chunk):
        """ Save a response chunk for later commit to backing store.
        """

    def close():
        """ Finish persisting the saved response to the backing store.
        """

class IPolicy(Interface):
    """ Reqired API of plugins which determine cacheability.
    """
    def fetch(environ):
        """ Determine whether a request can be served based on its 'environ'.

        o If not, return None.

        o If so, return a 3-tuple, '(status, headers, content)', where
          'status' and 'headers' will be passed to 'start_response', and
          'content' will be returned.
        """

    def store(status, headers, environ):
        """ Determine whether a response can be cached.

        o If not, return None.

        o If so, return an object implementing IChunkHandler, which will
          be used to store the response body after writing it.
        """

class IPolicyFactory(Interface):
    """ Required API of the entry point which creates a policy plugin.
    """
    def __call__(storage, config=None):
        """ Return a new policy plugin.
        
        o The new plugin should use the given 'storage' plugin as a 
          backing store.

        o 'config', if passed, will be a dictionary whose values may be
          used to configure the plugin.  By convention, the keys which
          are relevant to the plugin start with 'policy.'.
        """

class IStorage(Interface):
    """ Reqired API of plugins which manage the cache's backing store.
    """
    def fetch(url):
        """ Return a sequence of entries from the backing store for
        the given 'url'.  An entry is in the form (status, headers, body_iter,
        req_discrims, env_discrims).

        o Return None on a miss.
        """

    def store(url, status, headers, req_discrims, env_discrims):
        """ Prepare to cache a response to a backing store.

        o 'url' is the key for the response used during fetch.
          Two stored entries should "hash" to the same value
          if the tuple (url, req_discrims, env_discrims) is equal
          for both.
        
        o 'status' and 'headers' should be saved as well.

        o Return an object implementing IChunkHandler, which will
          be used to cache the response body chunks.
        """

class IStorageFactory(Interface):
    """ Required API of the entry point which creates a storage plugin.
    """
    def __call__(config=None):
        """ Return a new storage plugin.
        
        o 'config', if passed, will be a dictionary whose values may be
          used to configure the plugin.  By convention, the keys which
          are relevant to the plugin start with 'storage.'.
        """
