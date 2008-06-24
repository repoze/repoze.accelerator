from zope.interface import directlyProvides
from repoze.accelerator.interfaces import ILoggerFactory

def make_logger(config):
    import os
    import sys
    import logging

    if os.environ.get('ACCELERATOR_LOG'):
        log_stream = sys.stdout
        log_level = logging.DEBUG
        
    else:
        log_file = config.get('logger.filename', '')
        if not log_file or log_file.lower() == 'none':
            return None
        if log_file.lower() == 'stdout':
            log_stream = sys.stdout
        elif log_file.lower() == 'stderr':
            log_stream = sys.stderr
        else:
            log_stream = open(os.path.abspath(os.path.normpath(log_file)), 'a+')
        log_level = config.get('logger.log_level', 'INFO')
        log_level = log_level.upper()
        log_level = getattr(logging, log_level)

    handler = logging.StreamHandler(log_stream)
    fmt = '%(asctime)s %(message)s'
    formatter = logging.Formatter(fmt)
    handler.setFormatter(formatter)
    logger = logging.Logger('repoze.accelerator')
    logger.addHandler(handler)
    logger.setLevel(log_level)
    return logger
directlyProvides(make_logger, ILoggerFactory)
