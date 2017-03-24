
__all__ = ['get_netloc_port']


def get_netloc_port(scheme, netloc):
    try:
        netloc, port = netloc.split(':')
    except ValueError:
        if scheme == 'https':
            port = '443'
        else:
            port = '80'
    return netloc, port
