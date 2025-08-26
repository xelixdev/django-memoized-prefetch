from django.db import models
from seal.models import SealableModel


class SomeDifferentParentModel(SealableModel):
    name = models.CharField(max_length=100)


class SomeParentModel(SealableModel):
    name = models.CharField(max_length=255)

    some_parent_decimal = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    some_parent_date = models.DateField(auto_now=True, blank=True, null=True)
    some_parent_datetime = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        ordering = ("id",)


class SomeRelatedModel(SealableModel):
    name = models.CharField(max_length=255)


class SomeModel(SealableModel):
    name = models.CharField(max_length=255)
    some_parent_model = models.ForeignKey(
        SomeParentModel, on_delete=models.CASCADE, related_name="some_models", null=True
    )
    some_other_parent = models.ForeignKey(
        SomeParentModel, on_delete=models.CASCADE, related_name="some_other_models", blank=True, null=True
    )
    some_other_different_parent = models.ForeignKey(
        SomeDifferentParentModel, on_delete=models.CASCADE, blank=True, null=True
    )
    some_related_models = models.ManyToManyField(SomeRelatedModel, related_name="related_models")

    some_decimal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    some_date = models.DateField(auto_now=True)
    some_datetime = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)


class SomeChildModel(SealableModel):
    name = models.CharField(max_length=255)
    some_model = models.ForeignKey(SomeModel, on_delete=models.CASCADE, related_name="some_child_models")

    some_child_decimal = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    some_child_date = models.DateField(auto_now=True, blank=True, null=True)
    some_child_datetime = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        ordering = ("id",)
