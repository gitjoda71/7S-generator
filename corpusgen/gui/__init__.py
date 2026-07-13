"""Local web GUI for 7S-generator — standard library only.

`7s-generator gui` serves a single-file app on 127.0.0.1 and opens the
browser. Everything lives in this subpackage; the only hook in existing
code is the `gui` subcommand in cli.py.
"""
from .server import run  # noqa: F401
