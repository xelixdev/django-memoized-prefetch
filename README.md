# django-memoized-prefetch

A Django package that provides efficient memoized prefetching for processing data in chunks, reducing database queries through intelligent caching.
In some cases it can be useful even when not processing data in chunks, for example, when there are multiple foreign keys to the same table.

## Overview

`django-memoized-prefetch` optimizes Django ORM queries when processing large datasets by:
- **Reusing previously fetched objects** across chunks
- **Memoizing prefetched objects** using LRU (Least Recently Used) cache
- **Supporting both foreign key and many-to-many relationships**
- **Minimizing database queries** across chunk processing operations

## Installation

```bash
pip install django-memoized-prefetch
```

## Requirements

- Python 3.9+
- Django 4.2+
- lru-dict 1.3.0+

## Usage Examples

<details>
    <summary>Models used in examples, click to expand</summary>

```python
from django.db import models

class Author(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()

class Publisher(models.Model):
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=100)

class Category(models.Model):
    name = models.CharField(max_length=100)

class Book(models.Model):
    title = models.CharField(max_length=255)
    isbn = models.CharField(max_length=13)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    translator = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="translations", null=True)
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name="books")
    categories = models.ManyToManyField(Category, related_name="books")

class Review(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reviews")
    rating = models.IntegerField()
    comment = models.TextField()
```

</details>

### Basic Usage

Imagine you want to process all books, but there are too many of them to load them all into memory at once.
You therefore need to process them in chunks.

If you use just native django, it will look something like this:

```python
from chunkator import chunkator_page

for chunk in chunkator_page(Book.objects.all().prefetch_related("author", "translator", "publisher"), 10_000):
    for book in chunk:
        print(book.author.name, book.translator.name if book.translator is not None else None)
        print(book.publisher.name)
```

This will work, with two caveats:
1. On each chunk, Django will make separate queries to fetch the author and translator
2. The author, translator and publisher objects will be fetched from the database for each chunk

This is the primary usecase for this package. When used like this: 

```python
from django_memoized_prefetch import MemoizedPrefetch, MemoizedPrefetchConfig
from chunkator import chunkator_page

memoized_prefetch = MemoizedPrefetch(
    MemoizedPrefetchConfig(Author, ["author", "translator"]),
    MemoizedPrefetchConfig(Publisher, ["publisher"], prefetch_all=True),
)

for chunk in chunkator_page(Book.objects.all(), 10_000):
    memoized_prefetch.process_chunk(chunk)
    
    for book in chunk:
        print(book.author.name, book.translator.name if book.translator is not None else None)
        print(book.publisher.name)
```

The processing will be more efficient, because:
1. All publishers will get fetched before processing any chunks, and they will be reused across all chunks
2. The author and translator objects will be fetched using one query
3. Any authors and translators that appeared in previous chunks will not be fetched again 

#### Nested attributes

You can also prefetch nested attributes using both dotted notation and undersore notation, for example, in this example both would work.

```python
memoized_prefetch = MemoizedPrefetch(
    MemoizedPrefetchConfig(Publisher, ["book.publisher"]),
    MemoizedPrefetchConfig(Author, ["book__author"]),
)

for chunk in chunkator_page(Review.objects.all(), 10000):
    memoized_prefetch.process_chunk(chunk)
    ...
```

### Many-to-Many Relationships

Many-to-many relationships are supported as well, caching the target model, while fetching the through model for each chunk.

```python
from django_memoized_prefetch import MemoizedPrefetch, MemoizedPrefetchConfig
from chunkator import chunkator_page

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
```

### Usage outside chunked processing

If you have multiple foreign keys to the same table, this package can be used to optimise the database queries even when not processing data in chunks.

## Configuration Options

### MemoizedPrefetchConfig Parameters

- **`model`** (required): The Django model class to prefetch
- **`attributes`** (required): List of attribute names to prefetch on your objects
- **`queryset`** (optional): Custom queryset for the model (for additional select_related/prefetch_related)
- **`prefetch_all`** (optional, default: False): Whether to prefetch all objects at initialisation
- **`lru_cache_size`** (optional, default: 10,000): Maximum number of objects to keep in cache
- **`is_many_to_many`** (optional, default: False): Set to True for many-to-many relationships
- **`through_model`** (optional): Through model for many-to-many relationships
- **`source_field`** (optional): Source field name in the through model
- **`target_field`** (optional): Target field name in the through model

### Advanced Configuration

```python
from django.db import models

# Custom queryset with select_related
config = MemoizedPrefetchConfig(
    model=Author,
    attributes=["author"],
    queryset=Author.objects.select_related(...),
    lru_cache_size=5000,
)

# Prefetch all objects at startup (useful for small, frequently accessed tables)
config = MemoizedPrefetchConfig(
    model=Publisher,
    attributes=["publisher"],
    prefetch_all=True,
)
```

## Integrations with other packages.

The package automatically supports `django-seal` when available, all querysets which are sealable will be automatically sealed.

This package works when using `django-tenants`.

## Best Practices

1. **Use appropriate cache sizes**: Set `lru_cache_size` based on your expected data volume and available memory
2. **Prefetch related objects**: Use custom querysets with `select_related` or `prefetch_related` for nested relationships
3. **Consider prefetch_all**: Use `prefetch_all=True` for small, frequently accessed reference tables
4. **Process in reasonable chunks**: Balance memory usage with query efficiency when choosing chunk sizes
5. **Monitor cache hit rates**: Ensure your cache size is appropriate for your data access patterns

## Testing

Run the test suite:

```bash
uv run pytest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Authors

- Mikuláš Poul (mikulas.poul@xelix.com)
- Cameron Hobbs (cameron.hobbs@xelix.com)
