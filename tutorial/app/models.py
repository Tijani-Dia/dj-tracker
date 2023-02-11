from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=64)


class Author(models.Model):
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    date_of_birth = models.DateTimeField()
    date_of_death = models.DateTimeField(null=True, blank=True)
    biography = models.TextField()


class Book(models.Model):
    title = models.CharField(max_length=255)
    summary = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
