"""A registry of trained models for the tests that need one: trained once per run, with the fixed seed, in a folder removed at exit."""

import atexit
import functools
import tempfile

from xmart_analysis import cli

_FOLDER = tempfile.TemporaryDirectory()
atexit.register(_FOLDER.cleanup)


@functools.cache
def folder():
    assert cli.main(["learn", "--out", _FOLDER.name, "--now", "2026-11-15T00:00:00+00:00"]) == 0
    return _FOLDER.name
