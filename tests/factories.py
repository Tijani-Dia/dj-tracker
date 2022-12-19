import factory
from django.contrib.auth import get_user_model

from tests.models import Author, Book, Category, Comment, Place, TastyRestaurant


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"category-{n}")


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Sequence(lambda n: f"user-{n}")


class CommentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Comment

    comment = factory.Faker("text")
    user = factory.SubFactory(UserFactory)


class AuthorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Author

    user = factory.SubFactory(UserFactory)
    date_of_birth = factory.Faker("date_of_birth")
    date_of_death = factory.Faker("date_time_this_century")


class BookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Book

    title = factory.Faker("sentence", nb_words=4)
    summary = factory.Faker("paragraphs")
    category = factory.SubFactory(CategoryFactory)

    @factory.post_generation
    def authors(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            # A list of authors were passed in, use them
            for author in extracted:
                self.authors.add(author)


class PlaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Place

    name = factory.Sequence(lambda n: f"place-{n}")
    address = factory.Faker("address")


class TastyRestaurantFactory(PlaceFactory):
    class Meta:
        model = TastyRestaurant
