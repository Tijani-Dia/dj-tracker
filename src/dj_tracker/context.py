from contextvars import ContextVar

from dj_tracker.constants import DUMMY_REQUEST

request_var = ContextVar("request", default=DUMMY_REQUEST)


def get_request():
    return request_var.get()


def set_request(request):
    return request_var.set(request)


def reset_request(token):
    request_var.reset(token)
