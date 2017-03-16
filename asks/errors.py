'''
Simple exceptions to be raised in case of errors.
'''


class AsksException(Exception):
    '''
    Base exception for all asks errors.
    '''
    pass


class ConnectivityError(AsksException):
    pass


class TooManyRedirects(AsksException):
    pass


class RequestTimeout(ConnectivityError):
    pass


class ServerClosedConnectionError(ConnectivityError):
    pass
