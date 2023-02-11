import factory

from .models import Author, Book, Category


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Faker("word")


class AuthorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Author

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    date_of_birth = factory.Faker("date_of_birth")
    date_of_death = factory.Faker("date_time_this_century")
    biography = factory.Faker("text", max_nb_chars=5000)


class BookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Book

    title = factory.Faker("sentence")
    summary = factory.Faker("text", max_nb_chars=2500)
    author = factory.SubFactory(AuthorFactory)
    category = factory.SubFactory(CategoryFactory)


create_books = BookFactory.create_batch
