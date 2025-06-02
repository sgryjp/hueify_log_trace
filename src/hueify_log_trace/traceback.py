"""Colored traceback formatter with filtering capabilities.

This module provides utilities for formatting exception tracebacks with colored output.
The main component is:

- ``format_exception``: A function that formats exceptions with colored output

It extends Python's built-in traceback functionality by adding syntax highlighting
and filtering capabilities, making stack traces more readable in terminal environments.

The main function is ``format_exception``, which takes an exception instance and returns
a colorized string representation of the traceback, similar to the standard library's
``traceback.format_exception``, but with improved readability through color coding.

The module also supports filtering stack frames using regular expression patterns to
focus on relevant parts of the traceback.
"""

from __future__ import annotations

import io
import os
import re
from traceback import FrameSummary
from typing import IO, TYPE_CHECKING, Literal, NamedTuple, overload

from termcolor import colored

if TYPE_CHECKING:
    from collections.abc import Iterable


TracebackFilterEntry = tuple[Literal["show", "hide"], str | re.Pattern[str]]
"""A type alias for a tuple representing a single entry in the traceback filter."""


class _CompiledTracebackFilterEntry(NamedTuple):
    show: bool
    pattern: re.Pattern[str]


class TracebackFilter:
    r"""A class to filter stack frames in a traceback.

    This class allows you to specify which stack frames should be shown or hidden
    based on regular expression patterns. Entries in the filter are evaluated in order,
    and the first matching entry determines whether a frame is shown or hidden.
    If no entries match, the frame is shown by default.

    The matching is done by calling the `search` method of each regular expression
    pattern against the absolute file path of the stack frame.

    The absolute file path of the stack frame to be filtered typically varies depending
    on the execution environment. Therefore, it is recommended to create filtering
    conditions that reflect the runtime environment.
    For example, in an application that uses the ``requests`` package, to hide stack
    frames from the standard library and site-packages, you can specify the
    ``filter_rule`` with entries as follows.
    However, note that in this example the application itself is not excluded if it is
    installed in site-packages.

    .. code-block:: python
        import logging
        from pathlib import Path

        import requests

        import my_app

        stdlib_path = Path(logging.__file__).parents[1]
        site_packages_path = Path(requests.__file__).parents[1]
        filter_rule = [
            ("allow", re.escape(str(site_packages_path.joinpath("my_app")))),
            ("hide", re.escape(str(stdlib_path))),
            ("hide", re.escape(str(site_packages_path))),
        ]

    """

    def __init__(self, entries: Iterable[TracebackFilterEntry]) -> None:
        """Initialize the TracebackFilter with a list of filter rule entries."""
        self.entries = [
            _CompiledTracebackFilterEntry(
                type_ == "show",
                re.compile(pattern) if isinstance(pattern, str) else pattern,
            )
            for type_, pattern in entries
        ]

    def evaluate(self, filename: str) -> bool:
        """Evaluate whether a stack frame should be shown or not based on its filename.

        Parameters
        ----------
        filename : str
            The absolute file path of the stack frame.

        Returns
        -------
        bool
            Whether the frame should be shown or not.

        """
        for show, pattern in self.entries:
            if pattern.search(filename):
                return show
        return True


@overload
def format_exception(
    exc: BaseException,
    *,
    file: IO[str],
    traceback_filter: TracebackFilter | None = None,
) -> None: ...
@overload
def format_exception(
    exc: BaseException,
    *,
    file: None = None,
    traceback_filter: TracebackFilter | None = None,
) -> str: ...
def format_exception(
    exc: BaseException,
    *,
    file: IO[str] | None = None,
    traceback_filter: TracebackFilter | None = None,
) -> str | None:
    """Format exception information with colored output and optional filtering.

    This function formats the given exception's traceback and message in very similar
    format to the standard library's ``traceback.format_exception``, but with added
    colorization for better readability in terminal environments.

    If ``traceback_filter`` is provided, it will be used for filtering the stack frames
    based on the specified rules. The filtering rules are evaluated in the order they
    are provided, and the first matching rule determines whether a frame is shown or
    hidden. If no rules match, the frame is shown by default.

    Note that the path separators in the file paths are **normalized to forward slashes
    (`/`)** for consistency across different platforms. Specifically, when checking
    against the ``allow_list``, the absolute file paths are converted to POSIX format
    using ``Path.absolute().as_posix()``.

    Parameters
    ----------
    exc : BaseException
        The exception instance.

    file : IO[str] | None
        Optional file-like object to write to. If ``None``, returns a string.
        Defaults to ``None``.

    filter_rule : Iterable[TracebackFilterEntry] | None
        Optional sequence of filter rules to apply to the stack frames.

        Each entry should be a tuple of the form ``(type, pattern)``, where the ``type``
        is either ``"show"`` or ``"hide"``, and the ``pattern`` is a regular expression
        that matches the absolute file path of the stack frame.

        If ``None``, no filtering is applied, and all stack frames are shown.
        Defaults to ``None``.

    Returns
    -------
    str | None
        A str which is a printable representation of the exception if ``file`` is
        ``None``, otherwise `None`.

    """
    if file is None:
        with io.StringIO() as buffer:
            _format_exception(exc, file=buffer, traceback_filter=traceback_filter)
            return buffer.getvalue()
    _format_exception(exc, file=file, traceback_filter=traceback_filter)
    return None


def _format_exception(
    exc: BaseException,
    *,
    file: IO[str],
    traceback_filter: TracebackFilter | None = None,
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
        if traceback_filter is not None and traceback_filter.evaluate(filename):
            line = FrameSummary(filename, lineno, name).line
            file.write("    {}\n".format(colored(line, color="dark_grey")))

        tb = tb.tb_next

    type_name = re.sub(
        r"^builtins\.", "", f"{type(exc).__module__}.{type(exc).__name__}"
    )
    file.write(colored(f"{type_name}: {exc!s}", color="red"))
    file.flush()
