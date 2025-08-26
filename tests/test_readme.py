import pytest
from chunkator import chunkator_page

from django_memoized_prefetch import MemoizedPrefetch, MemoizedPrefetchConfig
from tests.test_project.bookshop.factories import BookFactory, ReviewFactory
from tests.test_project.bookshop.models import Author, Book, Category, Publisher, Review

pytestmark = pytest.mark.django_db


class TestReadmeExamples:
    @pytest.fixture(autouse=True)
    def setup(self):
        BookFactory.create_batch(100)
        ReviewFactory.create_batch(100)

    def test_basic_naive(self):
        for chunk in chunkator_page(Book.objects.all().prefetch_related("author", "translator", "publisher"), 10_000):
            for book in chunk:
                print(book.author.name, book.translator.name if book.translator is not None else None)
                print(book.publisher.name)

    def test_basic(self):
        memoized_prefetch = MemoizedPrefetch(
            MemoizedPrefetchConfig(Author, ["author", "translator"]),
            MemoizedPrefetchConfig(Publisher, ["publisher"], prefetch_all=True),
        )

        for chunk in chunkator_page(Book.objects.all(), 10_000):
            memoized_prefetch.process_chunk(chunk)

            for book in chunk:
                print(book.author.name, book.translator.name if book.translator is not None else None)
                print(book.publisher.name)

    def test_nested(self):
        memoized_prefetch = MemoizedPrefetch(
            MemoizedPrefetchConfig(Publisher, ["book.publisher"]),
            MemoizedPrefetchConfig(Author, ["book__author"]),
        )

        for chunk in chunkator_page(Review.objects.all(), 10000):
            memoized_prefetch.process_chunk(chunk)

    def test_m2m(self):
        # Configure for many-to-many relationships
        memoized_prefetch = MemoizedPrefetch(
            MemoizedPrefetchConfig(
                model=Category,
                attributes=["categories"],
                is_many_to_many=True,
                through_model=Book.categories.through,
                source_field="book_id",
                target_field="category_id",
            )
        )

        # Process books with their categories
        for chunk in chunkator_page(Book.objects.all(), 10000):
            memoized_prefetch.process_chunk(chunk)

            for book in chunk:
                # Categories are prefetched and available
                category_names = [cat.name for cat in book.categories.all()]
                print(f"Book: {book.title}, Categories: {', '.join(category_names)}")
