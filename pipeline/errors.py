"""Errors the ingest pipeline reports to the user with a clear message."""


class IngestError(RuntimeError):
    """A deterministic failure: the CLI prints it and exits non-zero."""
