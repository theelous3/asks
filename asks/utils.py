__all__ = ['get_netloc_port']


def get_netloc_port(scheme, netloc):
    try:
        netloc, port = netloc.split(':')
    except ValueError:
        if scheme == 'https':
            port = '443'
        else:
            port = '80'
    except TypeError:
        raise RuntimeError('Something is goofed. Contact the author!')
    return netloc, port
