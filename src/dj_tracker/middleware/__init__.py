from dj_tracker import context, tracker


def DjTrackerMiddleware(get_response):
    tracker.start()

    def middleware(request):
        token = context.set_request(request)
        response = get_response(request)
        context.reset_request(token)
        return response

    return middleware
