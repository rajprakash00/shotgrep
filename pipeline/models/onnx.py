"""The only door to onnxruntime.

The native runtime performs hardware discovery during import and, on some
virtualized hosts (GitHub's Azure runners among them), warns about PCI sysfs
entries through a C++ logger that Python severity settings cannot pre-empt.
Import it with the process's stderr briefly on /dev/null, then raise the
default severity to Error so later runtime warnings stay off the CLI's stderr.
Errors still surface: they raise, they do not write to stderr.
"""

from __future__ import annotations

import contextlib
import os
import sys


@contextlib.contextmanager
def _quiet_import():
    sys.stderr.flush()
    try:
        saved = os.dup(2)
    except OSError:
        yield
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        sys.stderr.flush()
        os.dup2(saved, 2)
        os.close(saved)
        os.close(devnull)


with _quiet_import():
    import onnxruntime as ort  # noqa: E402

ort.set_default_logger_severity(3)
