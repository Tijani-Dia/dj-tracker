from dj_tracker import tracker


def DjTrackerMiddleware(get_response):
    tracker.start()
    return get_response
