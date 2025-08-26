import itertools

import pytest
from dirty_equals import IsDict, IsList, IsPartialDict
from pytest_django import DjangoAssertNumQueries

from django_memoized_prefetch import MemoizedPrefetch, MemoizedPrefetchConfig
from tests.test_project.test_app.factories import (
    SomeChildModelFactory,
    SomeDifferentParentModelFactory,
    SomeModelFactory,
    SomeParentModelFactory,
    SomeRelatedModelFactory,
)
from tests.test_project.test_app.models import (
    SomeChildModel,
    SomeDifferentParentModel,
    SomeModel,
    SomeParentModel,
    SomeRelatedModel,
)

pytestmark = pytest.mark.django_db


class TestMemoizedPrefetch:
    @pytest.fixture(autouse=True)
    def some_different_parent_a(self) -> SomeDifferentParentModel:
        return SomeDifferentParentModelFactory()

    @pytest.fixture(autouse=True)
    def some_different_parent_b(self) -> SomeDifferentParentModel:
        return SomeDifferentParentModelFactory()

    @pytest.fixture(autouse=True)
    def parent_a(self) -> SomeParentModel:
        return SomeParentModelFactory()

    @pytest.fixture(autouse=True)
    def parent_b(self) -> SomeParentModel:
        return SomeParentModelFactory()

    @pytest.fixture(autouse=True)
    def objects_some_different_parent_a(
        self, parent_a: SomeParentModel, some_different_parent_a: SomeDifferentParentModel
    ) -> list[SomeModel]:
        return SomeModelFactory.create_batch(
            2, some_other_different_parent=some_different_parent_a, some_other_parent=None, some_parent_model=parent_a
        )

    @pytest.fixture(autouse=True)
    def objects_some_different_parent_b(
        self, parent_b: SomeParentModel, some_different_parent_b: SomeDifferentParentModel
    ) -> list[SomeModel]:
        return SomeModelFactory.create_batch(
            2, some_other_different_parent=some_different_parent_b, some_parent_model=parent_b
        )

    def test_param_validation(self):
        with pytest.raises(ValueError, match="Models have to be unique."):
            MemoizedPrefetch(
                MemoizedPrefetchConfig(SomeParentModel, ["some_parent_model"], prefetch_all=True),
                MemoizedPrefetchConfig(SomeParentModel, ["some_other_parent"], prefetch_all=True),
            )

    def test_memoized_prefetch(
        self,
        django_assert_num_queries: DjangoAssertNumQueries,
        django_assert_max_num_queries: DjangoAssertNumQueries,
        some_different_parent_a: SomeDifferentParentModel,
        some_different_parent_b: SomeDifferentParentModel,
        parent_a: SomeParentModel,
        parent_b: SomeParentModel,
    ):
        with django_assert_max_num_queries(2):  # fetch SomeParentModel + set schema
            memoized_prefetch = MemoizedPrefetch(
                MemoizedPrefetchConfig(SomeParentModel, ["some_parent_model"], prefetch_all=True),
                MemoizedPrefetchConfig(SomeDifferentParentModel, ["some_other_different_parent"]),
            )

        assert dict(memoized_prefetch.memoized_objects[SomeParentModel]) == IsPartialDict(
            {parent_a.id: parent_a, parent_b.id: parent_b}
        )
        assert dict(memoized_prefetch.memoized_objects[SomeDifferentParentModel]) == IsDict({})

        with django_assert_num_queries(2):  # one query to get objects, one to parents
            memoized_prefetch.process_chunk(
                SomeModel.objects.filter(some_other_different_parent=some_different_parent_a).seal()
            )

        assert dict(memoized_prefetch.memoized_objects[SomeDifferentParentModel]) == IsPartialDict(
            {some_different_parent_a.id: some_different_parent_a}
        )

        with django_assert_num_queries(1):  # one query to get objects, parents is already fetched
            memoized_prefetch.process_chunk(
                SomeModel.objects.filter(some_other_different_parent=some_different_parent_a).seal()
            )

        with django_assert_num_queries(2):  # one query to get objects, one to parents
            memoized_prefetch.process_chunk(
                SomeModel.objects.filter(some_other_different_parent=some_different_parent_b).seal()
            )

        assert dict(memoized_prefetch.memoized_objects[SomeDifferentParentModel]) == IsPartialDict(
            {some_different_parent_a.id: some_different_parent_a, some_different_parent_b.id: some_different_parent_b}
        )

        with django_assert_num_queries(1):  # one query to get objects, parents is already fetched
            memoized_prefetch.process_chunk(
                SomeModel.objects.filter(some_other_different_parent=some_different_parent_a).seal()
            )

        objects = list(SomeModel.objects.seal())

        with django_assert_num_queries(0):  # all parents already fetched
            memoized_prefetch.process_chunk(objects)

        assert objects

        for obj in objects:
            # does not throw seal attribute -> fetched in process_chunk
            assert obj.some_parent_model is not None
            assert obj.some_other_different_parent is not None

    @pytest.fixture
    def objects_with_m2m_set(self) -> list[SomeModel]:
        return SomeModelFactory.create_batch(
            10,
            some_parent_model=None,
            some_other_parent=None,
            some_related_models=SomeRelatedModelFactory.create_batch(2),
        )

    def test_memoized_prefetch_many_to_many(
        self, django_assert_num_queries: DjangoAssertNumQueries, objects_with_m2m_set: list[SomeModel]
    ) -> None:
        memoized_prefetch = MemoizedPrefetch(
            MemoizedPrefetchConfig(
                model=SomeRelatedModel,
                through_model=SomeModel.some_related_models.through,
                is_many_to_many=True,
                attributes=["some_related_models"],
                source_field="somemodel_id",
                target_field="somerelatedmodel_id",
            )
        )
        with django_assert_num_queries(3):
            qs = SomeModel.objects.filter(id__in=[obj.id for obj in objects_with_m2m_set]).seal()
            memoized_prefetch.process_chunk(qs)

        objects = list(SomeModel.objects.filter(id__in=[obj.id for obj in objects_with_m2m_set]).seal())

        with django_assert_num_queries(0):  # already fetched
            memoized_prefetch.process_chunk(objects)

        assert objects

        for obj in objects:
            related_models = list(obj.some_related_models.all())
            assert len(related_models) == 2
            assert all(rel_model.name for rel_model in related_models)

    def test_nullable_field(
        self,
        parent_a: SomeParentModel,
        parent_b: SomeParentModel,
        objects_some_different_parent_a,
        objects_some_different_parent_b,
    ):
        memoized_prefetch = MemoizedPrefetch(MemoizedPrefetchConfig(SomeParentModel, ["some_other_parent"]))

        objects = [*objects_some_different_parent_a, *objects_some_different_parent_b]
        objects = [SomeModel.objects.get(id=x.id) for x in objects]

        memoized_prefetch.process_chunk(objects)

        assert objects[0].some_other_parent is None
        assert objects[1].some_other_parent is None
        assert objects[2].some_other_parent is not None
        assert objects[3].some_other_parent is not None

    @pytest.fixture
    def child_models(self, objects_some_different_parent_a, objects_some_different_parent_b) -> list[SomeChildModel]:
        return [
            SomeChildModelFactory(some_model=some_model)
            for some_model in itertools.chain(objects_some_different_parent_a, objects_some_different_parent_b)
        ]

    def test_nested(self, child_models: list[SomeChildModel]):
        memoized_prefetch = MemoizedPrefetch(
            MemoizedPrefetchConfig(SomeParentModel, ["some_model__some_parent_model"], prefetch_all=True),
            MemoizedPrefetchConfig(
                SomeDifferentParentModel, ["some_model.some_other_different_parent"]
            ),  # support both . and __
        )

        objects = list(SomeChildModel.objects.select_related("some_model").seal())

        memoized_prefetch.process_chunk(objects)

        assert objects

        for obj in objects:
            # does not throw seal attribute -> fetched in process_chunk
            assert obj.some_model.some_parent_model is not None
            assert obj.some_model.some_other_different_parent is not None


class TestMemoizedPrefetchLRU:
    @pytest.fixture(autouse=True)
    def some_models(self) -> list[SomeModel]:
        # each has unique parent -> 20x parents
        return SomeModelFactory.create_batch(20)

    def test_memoized_prefetch_lru(
        self, django_assert_num_queries: DjangoAssertNumQueries, some_models: list[SomeModel]
    ):
        objects = list(SomeModel.objects.all().seal())
        some_models_map = {x.id: x for x in some_models}

        with django_assert_num_queries(0):
            memoized_prefetch = MemoizedPrefetch(
                MemoizedPrefetchConfig(SomeParentModel, ["some_parent_model"], lru_cache_size=10)
            )

        # completely fill the LRU cache

        with django_assert_num_queries(1):
            memoized_prefetch.process_chunk(objects[:10])

        for obj in objects[:10]:  # all still fetched
            assert obj.some_parent_model is not None  # does not throw seal attribute -> fetched in process_chunk
            assert obj.some_parent_model == some_models_map[obj.id].some_parent_model

        assert memoized_prefetch.memoized_objects[SomeParentModel].get_size() == 10  # cache size is 10

        # process objects with the 10 objects already in cache + 5 extra

        with django_assert_num_queries(1):  # fetches extra parents
            memoized_prefetch.process_chunk(objects[:15])

        for obj in objects[:15]:  # all still set correctly
            assert obj.some_parent_model is not None  # does not throw seal attribute -> fetched in process_chunk
            assert obj.some_parent_model == some_models_map[obj.id].some_parent_model

        assert memoized_prefetch.memoized_objects[SomeParentModel].get_size() == 10  # cache size is still 10
        assert len(memoized_prefetch.memoized_objects[SomeParentModel].values()) == 10

        # the values left in the cache are the last 10
        assert memoized_prefetch.memoized_objects[SomeParentModel].values() == IsList(
            *[obj.some_parent_model for obj in objects[5:15]], check_order=False
        )

    @pytest.fixture
    def some_models_with_related(self) -> list[SomeModel]:
        return SomeModelFactory.create_batch(
            20,
            some_parent_model=None,
            some_other_parent=None,
            some_related_models=SomeRelatedModelFactory.create_batch(2),
        )

    def test_memoized_prefetch_lru_m2m_related_ids(
        self, django_assert_num_queries: DjangoAssertNumQueries, some_models_with_related: list[SomeModel]
    ) -> None:
        memoized_prefetch = MemoizedPrefetch(
            MemoizedPrefetchConfig(
                model=SomeRelatedModel,
                through_model=SomeModel.some_related_models.through,
                is_many_to_many=True,
                attributes=["some_related_models"],
                source_field="somemodel_id",
                target_field="somerelatedmodel_id",
                lru_cache_size=10,
            )
        )
        objects = list(SomeModel.objects.filter(id__in=[obj.id for obj in some_models_with_related]).seal())
        # completely fill the LRU cache
        with django_assert_num_queries(2):
            memoized_prefetch.process_chunk(objects[:10])

        for obj in objects[:10]:  # all still fetched
            assert obj.some_related_models.all()  # does not throw seal attribute

        cache_key = "SomeModel_some_related_models_somemodel_id_somerelatedmodel_id"

        assert memoized_prefetch.through_model_source_target_cache[cache_key].get_size() == 10  # cache size is 10

        # process objects with the 10 objects already in cache + 5 extra
        with django_assert_num_queries(1):  # fetches extra parents
            memoized_prefetch.process_chunk(objects[:15])

        for obj in objects[:15]:  # all still set correctly
            assert obj.some_related_models.all()  # does not throw seal attribute

        assert memoized_prefetch.through_model_source_target_cache[cache_key].get_size() == 10  # cache size is 10
        assert len(memoized_prefetch.through_model_source_target_cache[cache_key].values()) == 10

        # the values left in the cache are the last 10
        assert memoized_prefetch.through_model_source_target_cache[cache_key].values() == IsList(
            *[[item.id for item in obj.some_related_models.all()] for obj in objects[5:15]], check_order=False
        )
