from contextvars import ContextVar

from dj_tracker.constants import DUMMY_REQUEST

request_var = ContextVar("request", default=DUMMY_REQUEST)
get_request = request_var.get
set_request = request_var.set
