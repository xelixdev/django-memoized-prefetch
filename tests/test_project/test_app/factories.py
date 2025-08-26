import factory

from tests.test_project.test_app.models import (
    SomeChildModel,
    SomeDifferentParentModel,
    SomeModel,
    SomeParentModel,
    SomeRelatedModel,
)


class SomeDifferentParentModelFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("pystr")

    class Meta:
        model = SomeDifferentParentModel


class SomeParentModelFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("pystr")

    some_parent_decimal = factory.Faker("pydecimal", left_digits=5, right_digits=2, positive=True)
    some_parent_date = factory.Faker("date")
    some_parent_datetime = factory.Faker("date_time")

    class Meta:
        model = SomeParentModel


class SomeRelatedModelFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("pystr")

    class Meta:
        model = SomeRelatedModel


class SomeModelFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("pystr")
    some_parent_model = factory.SubFactory(SomeParentModelFactory)
    some_other_parent = factory.SubFactory(SomeParentModelFactory)

    some_decimal = factory.Faker("pydecimal", left_digits=5, right_digits=2, positive=True)
    some_date = factory.Faker("date")
    some_datetime = factory.Faker("date_time")

    @factory.post_generation
    def some_related_models(self, create: bool, extracted: list[SomeRelatedModel]) -> None:
        if not create or not extracted:
            return

        if extracted:
            self.some_related_models.set(extracted)

    class Meta:
        model = SomeModel
        skip_postgeneration_save = True


class SomeChildModelFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("pystr")
    some_model = factory.SubFactory(SomeModelFactory)

    some_child_decimal = factory.Faker("pydecimal", left_digits=5, right_digits=2, positive=True)
    some_child_date = factory.Faker("date")
    some_child_datetime = factory.Faker("date_time")

    class Meta:
        model = SomeChildModel
