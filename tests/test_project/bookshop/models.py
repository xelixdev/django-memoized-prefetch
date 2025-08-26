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
