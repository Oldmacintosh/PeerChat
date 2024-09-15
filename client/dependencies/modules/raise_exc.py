# -*- coding: utf-8 -*-
"""
File that handles raising exceptions in the main thread from another
thread.
"""

from kivy.clock import mainthread


@mainthread
def _raise(exception) -> None:
    """
    Function to raise an exception in the main thread using the
    mainthread decorator.
    :param exception: Exception to raise.
    """
    raise exception


def raise_exception(func):
    """
    Decorator to raise an exception in the main thread.
    :param func: Function to decorate.
    :return: Decorated function.
    """

    def wrapper(*args, **kwargs):
        """
        Wrapper to raise an exception in the main thread.
        """
        try:
            func(*args, **kwargs)
        except Exception as error:
            _raise(error)

    return wrapper
