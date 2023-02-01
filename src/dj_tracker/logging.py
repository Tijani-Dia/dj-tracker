# https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output

import logging


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    green = "\x1b[32m'"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    log_format = "%(name)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: grey + log_format + reset,
        logging.INFO: green + log_format + reset,
        logging.WARNING: yellow + log_format + reset,
        logging.ERROR: red + log_format + reset,
        logging.CRITICAL: bold_red + log_format + reset,
    }

    def format(self, record):
        log_format = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_format)
        return formatter.format(record)


handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(CustomFormatter())

logger = logging.getLogger("dj_tracker")
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)
