import logging
import unittest

from dj_tracker.logging import logger

logger.setLevel(logging.INFO)


def teardown_tests(teardown):
    def wrapper(self):
        # Called once after all tests are executed.
        from dj_tracker import tracker

        tracker.stop()
        teardown(self)

    return wrapper


setattr(
    unittest.TestResult, "stopTestRun", teardown_tests(unittest.TestResult.stopTestRun)
)
