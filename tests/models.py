from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models


class User(AbstractUser):
    pass


class Category(models.Model):
    name = models.CharField(max_length=255, primary_key=True)


class Author(models.Model):
    user = models.OneToOneField(User, related_name="author", on_delete=models.CASCADE)
    date_of_birth = models.DateTimeField()
    date_of_death = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Comment(models.Model):
    comment = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()


class Book(models.Model):
    title = models.CharField(max_length=255)
    summary = models.TextField()
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="books"
    )
    authors = models.ManyToManyField(Author, related_name="books")
    comments = GenericRelation(Comment)

    def get_title_and_summary(self):
        return f"{self.title}-{self.summary}"
