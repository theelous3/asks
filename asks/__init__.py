# pylint: disable=wildcard-import
# pylint: disable=wrong-import-position

from .auth import *
from .base_funcs import *
from .sessions import *

from warnings import warn


def init(library):
    """
    Unused. asks+anyio auto-detects your library.
    """
    warn(
        "init is deprecated. asks + anyio now auto-detects" " your async library",
        DeprecationWarning,
    )
    pass
