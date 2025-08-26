import random

import factory

from tests.test_project.bookshop.models import (
    Author,
    Book,
    Category,
    Publisher,
    Review,
)


class AuthorFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("name")
    email = factory.Faker("email")

    class Meta:
        model = Author


class PublisherFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("company")
    country = factory.Faker("country")

    class Meta:
        model = Publisher


class CategoryFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("word")

    class Meta:
        model = Category


class BookFactory(factory.django.DjangoModelFactory):
    title = factory.Faker("sentence", nb_words=4)
    isbn = factory.Faker("isbn13")
    author = factory.SubFactory(AuthorFactory)
    translator = factory.SubFactory(AuthorFactory)
    publisher = factory.SubFactory(PublisherFactory)

    @factory.post_generation
    def categories(self, create: bool, extracted: list[Category]) -> None:
        if not create:
            return

        if extracted:
            self.categories.set(extracted)
        else:
            # Create 1-3 random categories if none provided
            categories = CategoryFactory.create_batch(random.randint(1, 3))
            self.categories.set(categories)

    class Meta:
        model = Book
        skip_postgeneration_save = True


class ReviewFactory(factory.django.DjangoModelFactory):
    book = factory.SubFactory(BookFactory)
    rating = factory.Faker("random_int", min=1, max=5)
    comment = factory.Faker("text", max_nb_chars=500)

    class Meta:
        model = Review
