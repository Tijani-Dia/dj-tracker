import time

from dj_tracker import constants
from dj_tracker.logging import logger
from dj_tracker.promise import QueryGroupPromise, QueryPromise, RequestPromise
from dj_tracker.utils import delay


class Collector:
    trackers = set()
    trackers_ready = []
    num_trackers = 0
    num_trackers_saved = 0

    requests = set()
    requests_ready = []
    num_requests = 0
    num_requests_saved = 0

    @classmethod
    def add_tracker(cls, tracker):
        cls.num_trackers += 1
        if not tracker.ready:
            cls.trackers.add(tracker)
        else:
            cls.trackers_ready.append(tracker)

    @classmethod
    def add_request(cls, request):
        cls.requests.add(request)
        cls.num_requests += 1

    @classmethod
    def tracker_ready(cls, tracker):
        # May not be in active yet for related querysets trackers,
        # or may have already been saved (when the worker stops).
        try:
            cls.trackers.remove(tracker)
        except KeyError:
            pass
        else:
            cls.trackers_ready.append(tracker)

    @classmethod
    def request_ready(cls, request):
        try:
            cls.requests.remove(request)
        except KeyError:
            pass
        else:
            cls.requests_ready.append(request)

    @classmethod
    @delay
    def save_trackers(cls):
        ready = cls.trackers_ready
        num_done = num_ready = len(ready)
        pks = set()
        add_query_id = pks.add
        pop_tracker = ready.pop

        while num_ready != 0:
            add_query_id(pop_tracker(0).save())
            num_ready -= 1

        QueryPromise.resolve()
        assert all(pk in QueryPromise.resolved for pk in pks)

        cls.num_trackers_saved += num_done

    @classmethod
    @delay
    def save_requests(cls):
        from dj_tracker.models import Tracking

        trackings = tuple(
            Tracking(
                started_at=request.started_at,
                request_id=RequestPromise.get_or_create(
                    path=request.path,
                    method=request.method,
                    content_type=request.content_type,
                    query_string=request.query_string,
                ),
                query_group_id=QueryGroupPromise.get_or_create(queries=request.queries),
            )
            for request in cls.requests_ready[:]
        )

        RequestPromise.resolve()
        QueryGroupPromise.resolve()
        delay(Tracking.objects.bulk_create)(trackings)

        len_trackings = len(trackings)
        cls.requests_ready[:len_trackings] = []
        cls.num_requests_saved += len_trackings

    @classmethod
    def run(cls):
        save_trackers = cls.save_trackers
        save_requests = cls.save_requests
        ready_trackers = cls.trackers_ready
        ready_requests = cls.requests_ready

        sleep = time.sleep
        sleep_for = constants.COLLECTION_INTERVAL
        stopping = constants.STOPPING.is_set

        logger.info("Collector running")

        while not stopping():
            sleep(sleep_for)
            if ready_trackers:
                save_trackers()
            if ready_requests:
                save_requests()

        iter_not_done = 0
        active_trackers = cls.trackers
        while active_trackers or ready_trackers:
            num_ready = len(ready_trackers)
            ready_trackers.extend(obj for obj in active_trackers if obj._iter_done)
            iter_not_done += len(active_trackers) - (len(ready_trackers) - num_ready)
            active_trackers.clear()
            save_trackers()

        ready_requests.extend(cls.requests)
        cls.requests.clear()
        if ready_requests:
            save_requests()

        assert cls.num_trackers_saved + iter_not_done == cls.num_trackers
        assert cls.num_requests_saved == cls.num_requests

        logger.info(f"Collector stopped: {cls.num_trackers_saved} queries tracked.")
