# pylint: disable=wildcard-import
# pylint: disable=wrong-import-position

from typing import Any
from warnings import warn

from .auth import *  # noqa
from .base_funcs import *  # noqa
from .sessions import *  # noqa


def init(library: Any) -> None:
    """
    Unused. asks+anyio auto-detects your library.
    """
    warn(
        "init is deprecated. asks + anyio now auto-detects" " your async library",
        DeprecationWarning,
    )
    pass
