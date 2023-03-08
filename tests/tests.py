import random
import unittest
from operator import attrgetter

from django import VERSION as DJANGO_VERSION
from django.test import TestCase
from django.urls import reverse

from dj_tracker.datastructures import QuerySetTracker, TrackedDict, TrackedSequence
from tests.factories import (
    AuthorFactory,
    BookFactory,
    CategoryFactory,
    CommentFactory,
    TastyRestaurantFactory,
    UserFactory,
)
from tests.models import Author, Book, Category, Comment, TastyRestaurant, User

get_instance_tracker = get_queryset_tracker = attrgetter("_tracker")


class TestAttributeTracker(TestCase):
    def test_track_attribute(self):
        CategoryFactory.create_batch(3)

        for category in Category.objects.all():
            tracker = get_instance_tracker(category)

            name = category.name
            self.assertEqual(category.name, name)
            self.assertEqual(tracker["name"].get, 2)
            self.assertEqual(tracker["name"].set, 0)

            category.name = "new-name"
            self.assertEqual(category.name, "new-name")
            self.assertEqual(tracker["name"].get, 3)
            self.assertEqual(tracker["name"].set, 1)

    def test_track_deferred_attribute(self):
        BookFactory()

        book = Book.objects.last()
        tracker = get_instance_tracker(book)
        self.assertIn("summary", tracker)
        self.assertIn("title", tracker)

        book = Book.objects.defer("summary", "title").last()
        tracker = get_instance_tracker(book)
        self.assertNotIn("summary", tracker)
        self.assertNotIn("title", tracker)

        title = book.title
        self.assertEqual(title, book.title)
        self.assertEqual(tracker["title"].get, 2)
        self.assertEqual(tracker["title"].set, 1)
        related_qs_tracker = tracker.queryset.related_querysets[0]
        self.assertIs(related_qs_tracker.related_queryset(), tracker.queryset)
        self.assertEqual(related_qs_tracker["field"], (Book, "title"))


class TestForwardManyToOneTracker(TestCase):
    def test_track_forward_many_to_one(self):
        category = CategoryFactory()
        BookFactory.create_batch(2, category=category)

        book = Book.objects.last()
        self.assertEqual(book.category, category)
        book.category = CategoryFactory()
        self.assertNotEqual(book.category, category)

        tracker = get_instance_tracker(book)
        self.assertEqual(tracker["category"].get, 2)
        self.assertEqual(tracker["category"].set, 1)

    def test_track_related(self):
        BookFactory()
        book = Book.objects.last()
        category = book.category
        self.assertEqual(
            get_instance_tracker(book).queryset,
            get_instance_tracker(category).queryset.related_queryset(),
        )


class TestForwardOneToOneTracker(TestCase):
    @classmethod
    def setUpTestData(cls):
        AuthorFactory()

    def test_track_forward_one_to_one(self):
        author = Author.objects.last()
        user = UserFactory()
        self.assertNotEqual(author.user, user)
        author.user = user
        self.assertEqual(author.user, user)
        author.user = None

        tracker = get_instance_tracker(author)
        self.assertEqual(tracker["user"].get, 2)
        self.assertEqual(tracker["user"].set, 2)

    def test_track_related(self):
        author = Author.objects.last()
        user = author.user
        self.assertEqual(
            get_instance_tracker(author).queryset,
            get_instance_tracker(user).queryset.related_queryset(),
        )


class TestReverseOneToOneTracker(TestCase):
    @classmethod
    def setUpTestData(cls):
        AuthorFactory()

    def test_track_forward_one_to_one(self):
        user = User.objects.last()
        author = AuthorFactory()

        self.assertNotEqual(user.author, author)
        self.assertEqual(user.author, user.author)

        tracker = get_instance_tracker(user)
        self.assertEqual(tracker["author"].get, 3)
        self.assertEqual(tracker["author"].set, 0)

    def test_track_related(self):
        user = User.objects.last()
        author = user.author
        self.assertEqual(
            get_instance_tracker(user).queryset,
            get_instance_tracker(author).queryset.related_queryset(),
        )


class TestReverseManyToOneTracker(TestCase):
    def test_track_reverse_many_to_one(self):
        category = CategoryFactory()
        BookFactory.create_batch(2, category=category)

        category = Category.objects.get(pk=category.pk)
        self.assertEqual(category.books.count(), 2)
        self.assertQuerysetEqual(
            Book.objects.filter(category=category), category.books.all(), ordered=False
        )

        tracker = get_instance_tracker(category)
        self.assertEqual(tracker["books"].get, 2)
        self.assertEqual(tracker["books"].set, 0)

    def test_track_related(self):
        BookFactory()

        category = Category.objects.last()
        books = category.books.all()
        self.assertEqual(len(books), 1)
        self.assertEqual(
            get_instance_tracker(category).queryset,
            get_instance_tracker(books[0]).queryset.related_queryset(),
        )


class TestManyToManyTracker(TestCase):
    @classmethod
    def setUpTestData(cls):
        authors = AuthorFactory.create_batch(3)
        for _ in range(3):
            BookFactory(authors=random.sample(authors, 2))

    def test_track_many_to_many(self):
        book = Book.objects.last()
        self.assertTrue(book.authors.all())

        for author in book.authors.iterator():
            self.assertIn(book, author.books.all())

            tracker = get_instance_tracker(author)
            self.assertEqual(tracker["books"].get, 1)
            self.assertEqual(tracker["books"].set, 0)

        tracker = get_instance_tracker(book)
        self.assertEqual(tracker["authors"].get, 2)
        self.assertEqual(tracker["authors"].set, 0)

    def test_track_related(self):
        book = Book.objects.last()
        author = book.authors.first()
        self.assertEqual(
            get_instance_tracker(book).queryset,
            get_instance_tracker(author).queryset.related_queryset(),
        )
        books = author.books.all()
        self.assertEqual(
            get_instance_tracker(author).queryset,
            get_instance_tracker(books[0]).queryset.related_queryset(),
        )


class TestGenericForeignKeyTracker(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.book = BookFactory()
        CommentFactory(content_object=cls.book)

    def test_track_generic_foreign_key(self):
        book = self.book
        comment = Comment.objects.last()

        self.assertEqual(comment.content_object, book)
        comment.content_object = BookFactory()
        self.assertNotEqual(comment.content_object, book)

        tracker = get_instance_tracker(comment)
        self.assertEqual(tracker["content_object"].get, 2)
        self.assertEqual(tracker["content_object"].set, 1)

    @unittest.expectedFailure
    def test_track_related(self):
        comment = Comment.objects.last()
        book = comment.content_object
        self.assertEqual(
            get_instance_tracker(comment).queryset,
            get_instance_tracker(book).queryset.related_queryset(),
        )


class TestReverseGenericManyToOneTracker(TestCase):
    @classmethod
    def setUpTestData(cls):
        book = BookFactory()
        CommentFactory.create_batch(2, content_object=book)

    def test_reverse_generic_many_to_one_tracker(self):
        book = Book.objects.last()

        self.assertEqual(book.comments.count(), 2)
        self.assertQuerysetEqual(
            Comment.objects.filter(object_id=book.pk),
            book.comments.all(),
            ordered=False,
        )

        tracker = get_instance_tracker(book)
        self.assertEqual(tracker["comments"].get, 2)
        self.assertEqual(tracker["comments"].set, 0)

    @unittest.expectedFailure
    def test_track_related(self):
        book = Book.objects.last()
        comments = book.comments.all()

        self.assertEqual(
            get_instance_tracker(book).queryset,
            get_instance_tracker(comments[0]).queryset.related_queryset(),
        )


class TestPrefetchRelated(TestCase):
    def test_prefetch_related(self):
        category = CategoryFactory()
        BookFactory.create_batch(3, category=category)
        BookFactory()

        with self.assertNumQueries(2):
            categories = Category.objects.prefetch_related("books").all()
            category = categories[0]
            category_tracker = get_instance_tracker(category)
            books = category.books.all()
            self.assertEqual(len(books), 3)

            book = books[0]
            book_tracker = get_instance_tracker(books[0])
            self.assertEqual(book.category, category)
            self.assertIs(
                category_tracker.queryset, book_tracker.queryset.related_queryset()
            )

            self.assertEqual(category_tracker["books"].get, 3)
            self.assertEqual(category_tracker["books"].set, 0)
            self.assertEqual(book_tracker["category"].get, 1)
            self.assertEqual(book_tracker["category"].set, 1)


class TestSelectRelated(TestCase):
    @classmethod
    def setUpTestData(cls):
        CommentFactory(content_object=BookFactory(), user=AuthorFactory().user)

    def test_select_related_fields(self):
        comment = Comment.objects.select_related("user__author", "content_type").last()

        with self.assertNumQueries(0):
            self.assertIsNotNone(get_instance_tracker(comment).queryset)

            self.assertIs(
                get_instance_tracker(comment.user).queryset,
                get_instance_tracker(comment).queryset,
            )

            self.assertIs(
                get_instance_tracker(comment.user.author).queryset,
                get_instance_tracker(comment.user).queryset,
            )

    def test_select_related(self):
        comment = Comment.objects.select_related().first()

        with self.assertNumQueries(0):
            self.assertIsNotNone(get_instance_tracker(comment).queryset)

            self.assertIs(
                get_instance_tracker(comment.user).queryset,
                get_instance_tracker(comment).queryset,
            )

            self.assertIs(
                get_instance_tracker(comment.content_type).queryset,
                get_instance_tracker(comment).queryset,
            )

        self.assertIs(
            get_instance_tracker(comment.user.author).queryset.related_queryset(),
            get_instance_tracker(comment).queryset,
        )

        # All related instances are tracked by one qs tracker.
        self.assertEqual(get_instance_tracker(comment).queryset["num_instances"], 3)


class TestCacheHits(TestCase):
    def test_cache_hits(self):
        AuthorFactory()

        for n in range(2, 5):
            with self.subTest(n=n):
                authors = Author.objects.all()
                for _ in range(n):
                    self.assertEqual(len(authors), 1)

                self.assertEqual(get_queryset_tracker(authors)["cache_hits"], 2 * n - 1)


class TestInstanceTracking(TestCase):
    def test_instances_tracking_occurences(self):
        BookFactory.create_batch(3)

        for book in Book.objects.all():
            self.assertTrue(book.title)
            self.assertEqual(get_instance_tracker(book)["title"].get, 1)

        queryset = get_instance_tracker(book).queryset
        self.assertEqual(len(queryset.instance_trackers[("", Book)]), 3)
        self.assertEqual(queryset["num_instances"], 3)


class TestValuesIterable(TestCase):
    def test_values(self):
        AuthorFactory.create_batch(3)

        objs = Author.objects.values()
        for obj in objs:
            self.assertIsInstance(obj, TrackedDict)
            obj["date_of_birth"]
            tracker = get_instance_tracker(obj)
            self.assertEqual(tracker["date_of_birth"].get, 1)
            self.assertEqual(tracker["date_of_birth"].set, 0)

        qs_tracker = get_queryset_tracker(objs)
        self.assertIsInstance(qs_tracker, QuerySetTracker)
        self.assertEqual(qs_tracker["num_instances"], 3)


class TestValuesListIterable(TestCase):
    def test_values_list(self):
        AuthorFactory.create_batch(3)

        objs = Author.objects.values_list()
        for obj in objs:
            self.assertIsInstance(obj, TrackedSequence)
            pk, user_id, date_of_birth, date_of_death = obj
            tracker = get_instance_tracker(obj)
            for i in range(4):
                self.assertEqual(tracker[str(i)].get, 1)
                self.assertEqual(tracker[str(i)].set, 0)

        qs_tracker = get_queryset_tracker(objs)
        self.assertIsInstance(qs_tracker, QuerySetTracker)
        self.assertEqual(qs_tracker["num_instances"], 3)

    def test_flat_values_list(self):
        BookFactory.create_batch(3)

        for attr, attr_type in (("id", int), ("title", str)):
            with self.subTest(attr=attr, type=attr_type):
                objs = Book.objects.values_list(attr, flat=True)
                for i, obj in enumerate(objs, start=1):
                    self.assertIsInstance(obj, attr_type)
                    self.assertFalse(hasattr(obj, "_tracker"))

                qs_tracker = get_queryset_tracker(objs)
                self.assertIsInstance(qs_tracker, QuerySetTracker)
                self.assertEqual(qs_tracker["num_instances"], 3)
                self.assertEqual(qs_tracker.num_ready, 3)


class TestCountHint(TestCase):
    def test_count_hint(self):
        AuthorFactory.create_batch(2)

        for len_calls in range(1, 5):
            qs = Author.objects.all()
            with self.subTest(len_calls=len_calls):
                for _ in range(len_calls):
                    self.assertEqual(len(qs), 2)

                qs_tracker = get_queryset_tracker(qs)
                self.assertEqual(qs_tracker["len_calls"], len_calls)
                self.assertEqual(qs_tracker["cache_hits"], 2 * len_calls - 1)


class TestContainsHint(TestCase):
    def test_contains_hint(self):
        AuthorFactory.create_batch(2)

        author = AuthorFactory()
        for contains_calls in range(1, 5):
            qs = Author.objects.all()
            qs._fetch_all()
            qs_tracker = get_queryset_tracker(qs)

            with self.subTest(contains_calls=contains_calls):
                for _ in range(contains_calls):
                    self.assertIn(author, qs)

                self.assertEqual(qs_tracker["contains_calls"], contains_calls)
                self.assertEqual(qs_tracker["cache_hits"], 2 * contains_calls)


class TestExistsHint(TestCase):
    def test_exists_hint(self):
        AuthorFactory()

        for exists_calls in range(1, 5):
            qs = Author.objects.all()
            qs._fetch_all()
            qs_tracker = get_queryset_tracker(qs)

            with self.subTest(exists_calls=exists_calls):
                for _ in range(exists_calls):
                    self.assertTrue(qs)

                self.assertEqual(qs_tracker["exists_calls"], exists_calls)
                self.assertEqual(qs_tracker["cache_hits"], 2 * exists_calls)


class TestIterator(TestCase):
    def test_iterator(self):
        AuthorFactory()

        qs = Author.objects.all()
        for el in qs.iterator():
            self.assertTrue(el)

        tracker = get_instance_tracker(el).queryset
        self.assertFalse(tracker.ready)
        el = None
        self.assertTrue(tracker.ready)


class TestRelatedField(TestCase):
    def test_related_field(self):
        BookFactory()
        book = Book.objects.get()
        category = book.category
        self.assertTrue(category)
        tracker = get_instance_tracker(category).queryset
        self.assertEqual(tracker["field"], (Book, "category"))

    def test_related_manager_field(self):
        category = CategoryFactory()
        BookFactory.create_batch(3, category=category)

        category = Category.objects.last()
        books = category.books.all()
        self.assertEqual(len(books), 3)
        tracker = get_queryset_tracker(books)
        self.assertEqual(tracker["field"], (Category, "books"))


class TestDepth(TestCase):
    def test_depth(self):
        BookFactory(authors=AuthorFactory.create_batch(2))
        book = Book.objects.get()
        category = book.category
        authors = book.authors.all()
        self.assertEqual(len(authors), 2)
        first_author_user = authors[0].user

        self.assertNotIn(
            "depth",
            get_instance_tracker(book).queryset,
        )
        self.assertEqual(get_instance_tracker(category).queryset["depth"], 1)
        self.assertEqual(get_queryset_tracker(authors)["depth"], 1)
        self.assertEqual(get_instance_tracker(first_author_user).queryset["depth"], 2)


class TestAttributesAccessed(TestCase):
    def test_attributes_accessed(self):
        authors = AuthorFactory.create_batch(3)
        for _ in range(2):
            BookFactory(authors=random.sample(authors, 2))

        qs = Book.objects.select_related("category")
        for obj in qs:
            self.assertTrue(obj.category)
            self.assertTrue(obj.title)
            self.assertEqual(obj.get_title_and_summary(), f"{obj.title}-{obj.summary}")

        attrs_accessed = get_queryset_tracker(qs)["attributes_accessed"]
        self.assertEqual(
            set(attrs_accessed.keys()), {"__dict__", "_state", "get_title_and_summary"}
        )
        self.assertEqual(attrs_accessed["get_title_and_summary"], len(qs))


class TestInheritance(TestCase):
    def test_inheritance(self):
        TastyRestaurantFactory()
        resto = TastyRestaurant.objects.get()
        self.assertTrue(resto.serves_pizza)
        self.assertEqual(get_instance_tracker(resto)["serves_pizza"].get, 1)
        self.assertEqual(get_instance_tracker(resto)["serves_pizza"].set, 0)

    if DJANGO_VERSION[0] < 4:
        # See descriptor issue solved in PR #14508.
        test_inheritance = unittest.expectedFailure(test_inheritance)


class TestM2MThroughModels(TestCase):
    def test_m2m_through_models_are_tracked(self):
        BookFactory(authors=AuthorFactory.create_batch(3))

        BookAuthors = Book.authors.through
        qs = BookAuthors.objects.all()
        self.assertEqual(len(qs), 3)
        for obj in qs:
            self.assertEqual(obj.book_id, 1)
            obj.author_id = 4
            tracker = get_instance_tracker(obj)
            self.assertEqual(tracker["book_id"].get, 1)
            self.assertEqual(tracker["book_id"].set, 0)
            self.assertEqual(tracker["author_id"].get, 0)
            self.assertEqual(tracker["author_id"].set, 1)

        qs_tracker = get_queryset_tracker(qs)
        self.assertEqual(qs_tracker["num_instances"], 3)
        self.assertEqual(qs_tracker["model"], BookAuthors)


class TestEmptyQueryset(TestCase):
    def test_empty_qs(self):
        qs = Book.objects.all()
        self.assertEqual(len(qs), 0)
        self.assertEqual(get_queryset_tracker(qs)["num_instances"], 0)


class TestTemplateInfo(TestCase):
    def test_get_traceback(self):
        BookFactory()
        response = self.client.get(reverse("books"))

        qs_tracker = get_queryset_tracker(response.context["books"])
        self.assertEqual(qs_tracker["num_instances"], 1)

        traceback, template_info = qs_tracker["traceback"]
        self.assertIn("/tests/templates/tests/books.html", template_info.filename)
        self.assertEqual(template_info.code, "{% for book in books %}")
