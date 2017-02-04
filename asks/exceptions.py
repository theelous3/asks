'''
Simple exceptions to be raised in case of errors.
'''


class TooManyRedirects(Exception):
    pass


class RequestTimeout(Exception):
    pass
