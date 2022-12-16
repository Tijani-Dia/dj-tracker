import random
import unittest

from django.test import TestCase

from dj_tracker import tracker
from dj_tracker.datastructures import (
    FieldTracker,
    QuerySetTracker,
    TrackedDict,
    TrackedSequence,
)
from dj_tracker.promise import FieldPromise, ModelPromise
from tests.factories import (
    AuthorFactory,
    BookFactory,
    CategoryFactory,
    CommentFactory,
    UserFactory,
)
from tests.models import Author, Book, Category, Comment, User


class DjTrackerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        tracker.start()


class TestAttributeTracker(DjTrackerTestCase):
    def test_track_attribute(self):
        for _ in range(3):
            CategoryFactory()

        for i, category in enumerate(Category.objects.all()):
            tracker = category._tracker

            name = category.name
            self.assertEqual(category.name, name)
            self.assertEqual(tracker["name"].get, 2)
            self.assertEqual(tracker["name"].set, 0)

            category.name = "new-name"
            self.assertEqual(category.name, "new-name")
            self.assertEqual(tracker["name"].get, 3)
            self.assertEqual(tracker["name"].set, 1)
            if i == 2:
                category.name

    def test_track_deferred_attribute(self):
        BookFactory()

        book = Book.objects.last()
        tracker = book._tracker
        self.assertIn("summary", tracker)
        self.assertIn("title", tracker)

        book = Book.objects.defer("summary", "title").last()
        tracker = book._tracker
        self.assertNotIn("summary", tracker)
        self.assertNotIn("title", tracker)

        title = book.title
        self.assertEqual(title, book.title)
        self.assertEqual(tracker["title"].get, 2)
        self.assertEqual(tracker["title"].set, 1)
        related_qs_tracker = tracker.queryset.related_querysets[0]
        self.assertIs(related_qs_tracker.related_queryset_id, tracker.queryset)
        self.assertEqual(
            related_qs_tracker.field_id,
            FieldPromise.get_or_create(
                name="title",
                model_id=ModelPromise.get_or_create(label=Book._meta.label),
            ),
        )


class TestForwardManyToOneTracker(DjTrackerTestCase):
    def test_track_forward_many_to_one(self):
        category = CategoryFactory()
        for _ in range(2):
            BookFactory(category=category)

        book = Book.objects.last()
        self.assertEqual(book.category, category)
        book.category = CategoryFactory()
        self.assertNotEqual(book.category, category)

        tracker = book._tracker
        self.assertEqual(tracker["category"].get, 2)
        self.assertEqual(tracker["category"].set, 1)

    def test_track_related(self):
        BookFactory()
        book = Book.objects.last()
        category = book.category
        self.assertEqual(
            book._tracker.queryset, category._tracker.queryset.related_queryset_id
        )


class TestForwardOneToOneTracker(DjTrackerTestCase):
    def test_track_forward_one_to_one(self):
        AuthorFactory()
        author = Author.objects.last()
        user = UserFactory()
        self.assertNotEqual(author.user, user)
        author.user = user
        self.assertEqual(author.user, user)
        author.user = None

        tracker = author._tracker
        self.assertEqual(tracker["user"].get, 2)
        self.assertEqual(tracker["user"].set, 2)

    def test_track_related(self):
        AuthorFactory()
        author = Author.objects.last()
        user = author.user
        self.assertEqual(
            author._tracker.queryset, user._tracker.queryset.related_queryset_id
        )


class TestReverseOneToOneTracker(DjTrackerTestCase):
    def test_track_forward_one_to_one(self):
        AuthorFactory()
        user = User.objects.last()
        author = AuthorFactory()

        self.assertNotEqual(user.author, author)
        self.assertEqual(user.author, user.author)

        tracker = user._tracker
        self.assertEqual(tracker["author"].get, 3)
        self.assertEqual(tracker["author"].set, 0)

    def test_track_related(self):
        AuthorFactory()
        user = User.objects.last()
        author = user.author
        self.assertEqual(
            user._tracker.queryset, author._tracker.queryset.related_queryset_id
        )


class TestReverseManyToOneTracker(DjTrackerTestCase):
    def test_track_reverse_many_to_one(self):
        category = CategoryFactory()
        for _ in range(2):
            BookFactory(category=category)

        category = Category.objects.get(pk=category.pk)
        self.assertEqual(category.books.count(), 2)
        self.assertQuerysetEqual(
            Book.objects.filter(category=category), category.books.all(), ordered=False
        )

        tracker = category._tracker
        self.assertEqual(tracker["books"].get, 2)
        self.assertEqual(tracker["books"].set, 0)

    def test_track_related(self):
        BookFactory()

        category = Category.objects.last()
        books = category.books.all()
        self.assertEqual(len(books), 1)
        self.assertEqual(
            category._tracker.queryset, books[0]._tracker.queryset.related_queryset_id
        )


class TestManyToManyTracker(DjTrackerTestCase):
    def test_track_many_to_many(self):
        authors = [AuthorFactory() for _ in range(3)]
        for _ in range(3):
            BookFactory(authors=random.sample(authors, 2))

        book = Book.objects.last()
        self.assertTrue(book.authors.all())

        for author in book.authors.iterator():
            self.assertIn(book, author.books.all())

            tracker = author._tracker
            self.assertEqual(tracker["books"].get, 1)
            self.assertEqual(tracker["books"].set, 0)

        tracker = book._tracker
        self.assertEqual(tracker["authors"].get, 2)
        self.assertEqual(tracker["authors"].set, 0)

    def test_track_related(self):
        authors = [AuthorFactory() for _ in range(3)]
        for _ in range(3):
            BookFactory(authors=random.sample(authors, 2))

        book = Book.objects.last()
        author = book.authors.first()
        self.assertEqual(
            book._tracker.queryset, author._tracker.queryset.related_queryset_id
        )
        books = author.books.all()
        self.assertEqual(
            author._tracker.queryset, books[0]._tracker.queryset.related_queryset_id
        )


class TestGenericForeignKeyTracker(DjTrackerTestCase):
    def test_track_generic_foreign_key(self):
        book = BookFactory()
        CommentFactory(content_object=book)
        comment = Comment.objects.last()

        self.assertEqual(comment.content_object, book)
        comment.content_object = BookFactory()
        self.assertNotEqual(comment.content_object, book)

        tracker = comment._tracker
        self.assertEqual(tracker["content_object"].get, 2)
        self.assertEqual(tracker["content_object"].set, 1)

    @unittest.expectedFailure
    def test_track_related(self):
        CommentFactory(content_object=BookFactory())
        comment = Comment.objects.last()
        book = comment.content_object
        self.assertEqual(
            comment._tracker.queryset, book._tracker.queryset.related_queryset_id
        )


class TestReverseGenericManyToOneTracker(DjTrackerTestCase):
    def test_reverse_generic_many_to_one_tracker(self):
        book = BookFactory()
        for _ in range(2):
            CommentFactory(content_object=book)
        book = Book.objects.last()

        self.assertEqual(book.comments.count(), 2)
        self.assertQuerysetEqual(
            Comment.objects.filter(object_id=book.pk),
            book.comments.all(),
            ordered=False,
        )

        tracker = book._tracker
        self.assertEqual(tracker["comments"].get, 2)
        self.assertEqual(tracker["comments"].set, 0)

    @unittest.expectedFailure
    def test_track_related(self):
        book = BookFactory()
        for _ in range(2):
            CommentFactory(content_object=book)

        book = Book.objects.last()
        comments = book.comments.all()
        self.assertEqual(
            book._tracker.queryset, comments[0]._tracker.queryset.related_queryset_id
        )


class TestPrefetchRelated(DjTrackerTestCase):
    def test_prefetch_related(self):
        category = CategoryFactory()
        BookFactory()
        for _ in range(3):
            BookFactory(category=category)

        with self.assertNumQueries(2):
            categories = Category.objects.prefetch_related("books").all()
            category = categories[0]
            category_tracker = category._tracker
            books = category.books.all()
            self.assertEqual(len(books), 3)

            book = books[0]
            book_tracker = books[0]._tracker
            self.assertEqual(book.category, category)
            self.assertIs(
                category_tracker.queryset, book_tracker.queryset.related_queryset_id
            )

            self.assertEqual(category_tracker["books"].get, 3)
            self.assertEqual(category_tracker["books"].set, 0)
            self.assertEqual(book_tracker["category"].get, 1)
            self.assertEqual(book_tracker["category"].set, 1)


class TestSelectRelated(DjTrackerTestCase):
    def test_select_related_fields(self):
        CommentFactory(content_object=BookFactory(), user=AuthorFactory().user)
        comment = Comment.objects.select_related("user__author", "content_type").last()

        with self.assertNumQueries(0):
            self.assertIsNotNone(comment._tracker.queryset)

            self.assertIs(comment.user._tracker.queryset, comment._tracker.queryset)

            self.assertIs(
                comment.user.author._tracker.queryset,
                comment.user._tracker.queryset,
            )

    def test_select_related(self):
        CommentFactory(content_object=BookFactory(), user=AuthorFactory().user)
        comment = Comment.objects.select_related().last()

        with self.assertNumQueries(0):
            self.assertIsNotNone(comment._tracker.queryset)

            self.assertIs(comment.user._tracker.queryset, comment._tracker.queryset)

            self.assertIs(
                comment.content_type._tracker.queryset,
                comment._tracker.queryset,
            )

        self.assertIs(
            comment.user.author._tracker.queryset.related_queryset_id,
            comment._tracker.queryset,
        )


class TestCacheHits(DjTrackerTestCase):
    def test_cache_hits(self):
        AuthorFactory()

        for n in range(2, 5):
            with self.subTest(n=n):
                authors = Author.objects.all()
                for _ in range(n):
                    self.assertEqual(len(authors), 1)

                self.assertEqual(authors._tracker.cache_hits, 2 * n - 1)


class TestInstanceTracking(DjTrackerTestCase):
    def test_instances_tracking_occurences(self):
        for _ in range(3):
            BookFactory()

        for book in Book.objects.all():
            self.assertTrue(book.title)
            self.assertEqual(book._tracker["title"].get, 1)

        queryset = book._tracker.queryset
        self.assertEqual(len(queryset.instance_trackers[("", Book)]), 3)
        self.assertEqual(queryset.num_instances, 3)

        book = None  # Clear reference
        """gc.collect()
        instance_trackings = None

        def _set_instance_trackings():
            while queryset.id is None:
                time.sleep(0.01)

            nonlocal instance_trackings
            while not (instance_trackings := list(queryset.instances.all())):
                time.sleep(0.01)

        t = threading.Thread(target=_set_instance_trackings, daemon=True)
        t.start()
        t.join(timeout=1.5)

        self.assertEqual(len(instance_trackings), 1)
        self.assertEqual(instance_trackings[0].num_occurrences, 3)"""


class TestValuesIterable(DjTrackerTestCase):
    def test_values(self):
        for _ in range(3):
            AuthorFactory()

        objs = Author.objects.values()
        for obj in objs:
            self.assertIsInstance(obj, TrackedDict)
            obj["date_of_birth"]
            tracker = obj._tracker
            self.assertEqual(tracker["date_of_birth"], FieldTracker(get=1, set=0))

        qs_tracker = objs._tracker
        self.assertIsInstance(qs_tracker, QuerySetTracker)
        self.assertEqual(qs_tracker.num_instances, 3)


class TestValuesListIterable(DjTrackerTestCase):
    def test_values_list(self):
        for _ in range(3):
            AuthorFactory()

        objs = Author.objects.values_list()
        for obj in objs:
            self.assertIsInstance(obj, TrackedSequence)
            pk, user_id, date_of_birth, date_of_death = obj
            tracker = obj._tracker
            for i in range(4):
                self.assertEqual(tracker[str(i)], FieldTracker(get=1, set=0))

        qs_tracker = objs._tracker
        self.assertIsInstance(qs_tracker, QuerySetTracker)
        self.assertEqual(qs_tracker.num_instances, 3)

    def test_flat_values_list(self):
        for _ in range(3):
            BookFactory()

        for attr, attr_type in (("id", int), ("title", str)):
            with self.subTest(attr=attr, type=attr_type):
                objs = Book.objects.values_list(attr, flat=True)
                for i, obj in enumerate(objs, start=1):
                    self.assertIsInstance(obj, attr_type)
                    self.assertFalse(hasattr(obj, "_tracker"))

                qs_tracker = objs._tracker
                self.assertIsInstance(qs_tracker, QuerySetTracker)
                self.assertEqual(qs_tracker.num_instances, 3)


class TestCountHint(DjTrackerTestCase):
    def test_count_hint(self):
        for _ in range(2):
            AuthorFactory()
        for len_calls in range(1, 5):
            qs = Author.objects.all()
            with self.subTest(len_calls=len_calls):
                for _ in range(len_calls):
                    self.assertEqual(len(qs), 2)

                qs_tracker = qs._tracker
                self.assertEqual(qs_tracker.len_calls, len_calls)
                self.assertEqual(qs_tracker.cache_hits, 2 * len_calls - 1)


class TestContainsHint(DjTrackerTestCase):
    def test_contains_hint(self):
        for _ in range(2):
            AuthorFactory()

        author = AuthorFactory()
        for contains_calls in range(1, 5):
            qs = Author.objects.all()
            qs._fetch_all()
            qs_tracker = qs._tracker

            with self.subTest(contains_calls=contains_calls):
                for _ in range(contains_calls):
                    self.assertIn(author, qs)

                self.assertEqual(qs_tracker.contains_calls, contains_calls)
                self.assertEqual(qs_tracker.cache_hits, 2 * contains_calls)


class TestExistsHint(DjTrackerTestCase):
    def test_exists_hint(self):
        AuthorFactory()
        for exists_calls in range(1, 5):
            qs = Author.objects.all()
            qs._fetch_all()
            qs_tracker = qs._tracker

            with self.subTest(exists_calls=exists_calls):
                for _ in range(exists_calls):
                    self.assertTrue(qs)

                self.assertEqual(qs_tracker.exists_calls, exists_calls)
                self.assertEqual(qs_tracker.cache_hits, 2 * exists_calls)


class TestIterator(DjTrackerTestCase):
    def test_iterator(self):
        AuthorFactory()
        qs = Author.objects.all()
        for el in qs.iterator():
            self.assertTrue(el)

        tracker = el._tracker.queryset
        self.assertFalse(tracker.ready)
        el = None
        self.assertTrue(tracker.ready)


class TestRelatedField(DjTrackerTestCase):
    def test_related_field(self):
        BookFactory()
        book = Book.objects.get()
        category = book.category
        self.assertTrue(category)
        tracker = category._tracker.queryset
        self.assertEqual(
            tracker.field_id,
            FieldPromise.get_or_create(
                model_id=ModelPromise.get_or_create(label=Book._meta.label),
                name="category",
            ),
        )

    def test_related_manager_field(self):
        category = CategoryFactory()
        for _ in range(3):
            BookFactory(category=category)

        category = Category.objects.last()
        books = category.books.all()
        self.assertEqual(len(books), 3)
        tracker = books._tracker
        self.assertEqual(
            tracker.field_id,
            FieldPromise.get_or_create(
                model_id=ModelPromise.get_or_create(label=Category._meta.label),
                name="books",
            ),
        )


class TestDepth(DjTrackerTestCase):
    def test_depth(self):
        BookFactory(authors=[AuthorFactory() for _ in range(2)])
        book = Book.objects.get()
        category = book.category
        authors = book.authors.all()
        self.assertEqual(len(authors), 2)
        first_author_user = authors[0].user

        self.assertEqual(book._tracker.queryset.depth, 0)
        self.assertEqual(category._tracker.queryset.depth, 1)
        self.assertEqual(authors._tracker.depth, 1)
        self.assertEqual(first_author_user._tracker.queryset.depth, 2)


class TestAttributesAccessed(DjTrackerTestCase):
    def test_attributes_accessed(self):
        for _ in range(2):
            BookFactory(authors=[AuthorFactory() for _ in range(2)])

        qs = Book.objects.select_related("category")
        for obj in qs:
            self.assertTrue(obj.category)
            self.assertTrue(obj.title)
            self.assertEqual(obj.get_title_and_summary(), f"{obj.title}-{obj.summary}")

        attrs_accessed = qs._tracker._attributes_accessed
        len_qs = len(qs)

        self.assertEqual(
            set(attrs_accessed),
            {
                "__dict__",
                "_state",
                "_tracker",
                "title",
                "category",
                "summary",
                "get_title_and_summary",
            },
        )
        self.assertEqual(attrs_accessed["__dict__"], 0)
        self.assertEqual(attrs_accessed["_state"], 0)
        self.assertEqual(attrs_accessed["category"], len_qs)
        self.assertEqual(attrs_accessed["get_title_and_summary"], len_qs)
        self.assertEqual(attrs_accessed["title"], 3 * len_qs)
        self.assertEqual(attrs_accessed["summary"], 2 * len_qs)
