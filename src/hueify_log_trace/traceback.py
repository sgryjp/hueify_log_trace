"""Colored traceback formatter with filtering capabilities.

This module provides utilities for formatting exception tracebacks with colored output.
The main component is:

- `format_exception`: A function that formats exceptions with colored output

It extends Python's built-in traceback functionality by adding syntax highlighting
and filtering capabilities, making stack traces more readable in terminal environments.

The main function is ``format_exception``, which takes an exception instance and returns
a colorized string representation of the traceback, similar to the standard library's
``traceback.format_exception``, but with improved readability through color coding.

The module also supports filtering stack frames using regex patterns to focus on
relevant parts of the traceback.
"""

from __future__ import annotations

import io
import os
import re
from functools import lru_cache
from pathlib import Path
from re import Pattern
from traceback import FrameSummary
from typing import IO, TYPE_CHECKING, overload

from termcolor import colored

if TYPE_CHECKING:
    from collections.abc import Sequence


@overload
def format_exception(
    exc: BaseException,
    *,
    file: IO[str],
    allow_list: Sequence[Pattern[str] | str] | None = None,
    deny_list: None = None,
) -> None: ...
@overload
def format_exception(
    exc: BaseException,
    *,
    file: IO[str],
    allow_list: None = None,
    deny_list: Sequence[Pattern[str] | str] | None = None,
) -> None: ...
@overload
def format_exception(
    exc: BaseException,
    *,
    file: None = None,
    allow_list: Sequence[Pattern[str] | str] | None = None,
    deny_list: None = None,
) -> str: ...
@overload
def format_exception(
    exc: BaseException,
    *,
    file: None = None,
    allow_list: None = None,
    deny_list: Sequence[Pattern[str] | str] | None = None,
) -> str: ...
def format_exception(
    exc: BaseException,
    *,
    file: IO[str] | None = None,
    allow_list: Sequence[Pattern[str] | str] | None = None,
    deny_list: Sequence[Pattern[str] | str] | None = None,
) -> str | None:
    """Format exception information with colored output and optional filtering.

    This function formats the given exception's traceback and message in very similar
    format to the standard library's `traceback.format_exception`, but with added
    colorization for better readability in terminal environments.

    The filtering process is as follows:

    1. If `allow_list` is provided, only stack frames of which absolute file paths match
       any of the patterns in `allow_list` will be included.
    2. If `deny_list` is provided, stack frames of which absolute file paths match
       any of the patterns in `deny_list` will be excluded from the output.
    3. If both `allow_list` and `deny_list` are provided, this function will raise a
       `ValueError`.

    Note that the path separators in the file paths are **normalized to forward slashes
    (``/``)** for consistency across different platforms. Specifically, when checking
    against the `allow_list`, the absolute file paths are converted to POSIX format
    using `Path.absolute().as_posix()`.

    Parameters
    ----------
    exc : BaseException
        The exception instance.

    file : IO[str] | None, default=None
        Optional file-like object to write to. If ``None``, returns a string.

    allow_list : Sequence[Pattern[str] | str] | None, default=None
        Optional sequence of regular expression patterns to filter stack frames.

    Returns
    -------
    str | None
        A printable string representation of the exception if ``file`` is None,
        otherwise ``None``.

    """
    if allow_list is not None and deny_list is not None:
        msg = "Cannot use both `allow_list` and `deny_list` at the same time."
        raise ValueError(msg)

    if deny_list is not None:
        raise NotImplementedError  # TODO: Implement deny_list filtering

    if file is None:
        with io.StringIO() as buffer:
            _format_exception(exc, file=buffer, allow_list=allow_list)
            return buffer.getvalue()
    _format_exception(exc, file=file, allow_list=allow_list)
    return None


def _format_exception(
    exc: BaseException,
    *,
    file: IO[str],
    allow_list: Sequence[Pattern[str] | str] | None = None,
) -> None:
    file.write("Traceback (most recent call last):\n")

    tb = exc.__traceback__
    while tb is not None:
        frame = tb.tb_frame
        code = frame.f_code
        filename = code.co_filename
        name = code.co_name
        lineno = tb.tb_lineno

        dirname, basename = os.path.split(filename)
        linked_location = "File {}{}{}, line {}, in {}".format(
            colored('"' + dirname + os.sep, color="light_grey"),
            colored(basename, color="light_grey", attrs=["bold"]),
            colored('"', color="light_grey"),
            colored(lineno, color="magenta"),
            colored(name, color="magenta"),
        )
        file.write(f"  {linked_location}\n")
        if allow_list is None or _check_allow_list(allow_list, filename):
            line = FrameSummary(filename, lineno, name).line
            file.write("    {}\n".format(colored(line, color="dark_grey")))

        tb = tb.tb_next

    type_name = re.sub(
        r"^builtins\.", "", f"{type(exc).__module__}.{type(exc).__name__}"
    )
    file.write(colored(f"{type_name}: {exc!s}", color="red"))
    file.flush()


@lru_cache(maxsize=128)
def _check_allow_list(allow_list: Sequence[Pattern[str] | str], filename: str) -> bool:
    path = Path(filename).absolute().as_posix()  # Normalize the path for consistency
    return any(pattern.search(path) for pattern in _compile_all(allow_list))


def _compile_all(allow_list: Sequence[Pattern[str] | str]) -> Sequence[Pattern[str]]:
    # Note that compiled regex patterns are cached in Python.
    return [re.compile(s) for s in allow_list]
