"""Tests for finder/logcapture.py — collecting pipeline warnings in a batch run."""

import logging

from finder.logcapture import capture_warnings
from utils.logger import logger


class TestCaptureWarnings:
    def test_warnings_are_collected(self):
        with capture_warnings() as warnings:
            logger.warning("3 havola inglizcha qoldi")
        assert warnings == ["3 havola inglizcha qoldi"]

    def test_info_is_not_collected(self):
        with capture_warnings() as warnings:
            logger.info("just progress")
            logger.warning("a real problem")
        assert warnings == ["a real problem"]

    def test_errors_are_collected_too(self):
        with capture_warnings() as warnings:
            logger.fail("Tahrir xatosi")
        assert len(warnings) == 1
        assert "Tahrir xatosi" in warnings[0]

    def test_list_is_filled_during_the_block(self):
        with capture_warnings() as warnings:
            logger.warning("first")
            assert warnings == ["first"]
            logger.warning("second")
        assert warnings == ["first", "second"]

    def test_handler_is_removed_afterwards(self):
        log = logging.getLogger("WikiTranslator")
        before = len(log.handlers)
        with capture_warnings():
            assert len(log.handlers) == before + 1
        assert len(log.handlers) == before

    def test_handler_removed_even_when_the_block_raises(self):
        log = logging.getLogger("WikiTranslator")
        before = len(log.handlers)
        try:
            with capture_warnings():
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert len(log.handlers) == before

    def test_a_quiet_logger_is_temporarily_opened_up(self):
        log = logging.getLogger("WikiTranslator")
        original = log.level
        log.setLevel(logging.CRITICAL)
        try:
            with capture_warnings() as warnings:
                logger.warning("would normally be suppressed")
            assert warnings == ["would normally be suppressed"]
            assert log.level == logging.CRITICAL
        finally:
            log.setLevel(original)
