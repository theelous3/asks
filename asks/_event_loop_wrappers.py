__all__ = ['trio_open_connection', 'trio_send_all', 'trio_receive_some',
           'curio_sendall', 'curio_recv']

from contextlib import contextmanager

import trio


# trio wrappers

async def trio_open_connection(host, port, *, ssl=False, **kwargs):
    if not ssl:
        sock = await trio.open_tcp_stream(host, port)
    else:
        sock = await trio.open_ssl_over_tcp_stream(host, port)
        await sock.do_handshake()
    return sock


async def trio_send_all(sock, *args, **kwargs):
    await sock.send_all(*args, **kwargs)


async def trio_receive_some(sock, max_bytes):
    return (await sock.receive_some(max_bytes))


# curio wrappers

async def curio_sendall(sock, *args, **kwargs):
    await sock.sendall(*args, **kwargs)


async def curio_recv(sock, max_bytes):
    return (await sock.recv(max_bytes))
