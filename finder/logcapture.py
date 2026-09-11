#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
finder/logcapture.py - Collect the pipeline's warnings instead of losing them.

Several things the human needs to know about a translation are reported only
as console warnings inside core/processor.py: links whose target stayed
English, references whose placeholder never came back. main.py prints them
and moves on; in a batch run nobody is watching the console.

utils/logger.py wraps the stdlib logger "WikiTranslator", so a temporary
handler picks all of them up verbatim without touching processor.py.
"""

import logging
from contextlib import contextmanager
from typing import Iterator, List

LOGGER_NAME = "WikiTranslator"


class _Collector(logging.Handler):
    def __init__(self, level: int):
        super().__init__(level)
        self.messages: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@contextmanager
def capture_warnings(level: int = logging.WARNING) -> Iterator[List[str]]:
    """
    Collect everything the pipeline logs at `level` or above.

    The list is filled as the block runs, so it is complete by the time the
    block exits:

        with capture_warnings() as warnings:
            result = run_pipeline(...)
        # warnings now holds every WARNING/ERROR the run produced
    """
    handler = _Collector(level)
    log = logging.getLogger(LOGGER_NAME)

    # The logger's own level gates records before any handler sees them, so a
    # run with LOG_LEVEL=ERROR would otherwise capture nothing.
    previous_level = log.level
    if previous_level > level:
        log.setLevel(level)

    log.addHandler(handler)
    try:
        yield handler.messages
    finally:
        log.removeHandler(handler)
        log.setLevel(previous_level)
