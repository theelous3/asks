'''
Simple exceptions to be raised in case of errors.
'''


class AsksException(Exception):
    '''
    Base exception for all asks errors.
    '''
    pass


class TooManyRedirects(AsksException):
    pass


class ConnectivityError(AsksException):
    '''
    Base exception for network failure errors.
    '''
    pass


class BadHttpResponse(AsksException):
    pass


class RequestTimeout(ConnectivityError):
    pass


class ServerClosedConnectionError(ConnectivityError):
    pass
