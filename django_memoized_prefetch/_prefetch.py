from __future__ import annotations

__all__ = ["MemoizedPrefetch"]

from collections import defaultdict

from django.db import models
from lru import LRU

from ._config import MemoizedPrefetchConfig
from ._dotted_getattr import dotted_getattr


class MemoizedPrefetch:
    """
    A class that utilises efficient prefetching when processing data in chunks. Given a list of prefetch configurations,
    when processing individual chunks in `process_chunk` method, the class will prefetch new objects which are required
    and reuse objects fetched in previous chunks (up to a limit).

    See MemoizedPrefetchConfig for description of the parameters. See TestMemoizedPrefetch for usage example.

    MemoizedPrefetch is not as lazy as normal django, so just initialising can make queries, if you for example
    use a MemoizedPrefetchConfig with `prefetch_all=True`.
    """

    def __init__(self, *configs: MemoizedPrefetchConfig):
        self.memoized_objects: dict[type[models.Model], LRU[int, models.Model]] = {}
        self.memoized_objects_configs: dict[type[models.Model], MemoizedPrefetchConfig] = {}
        self.through_model_source_target_cache: dict[str, LRU[int, list[int]]] = {}

        for config in configs:
            if config.model in self.memoized_objects_configs:
                msg = (
                    "Models have to be unique. If you need to fetch the same model for multiple attributes, "
                    "put the multiple attributes in the list of attributes."
                )
                raise ValueError(msg)

            self.memoized_objects_configs[config.model] = config
            self.memoized_objects[config.model] = LRU(config.lru_cache_size)

            if config.prefetch_all:
                # can't use in_bulk with limiting the queryset to cache size
                self.memoized_objects[config.model].update(
                    {x.id: x for x in config.get_queryset()[: config.lru_cache_size]}
                )

    def _get_m2m_related_ids(self, obj_ids: list[int], config: MemoizedPrefetchConfig) -> LRU:
        # Maps source ids (model) to target ids (through model target), and updates cache
        if not config.through_model or not config.source_field or not config.target_field:
            msg = "If is_many_to_many is True, through_model, source_field, and target_field must be provided."
            raise ValueError(msg)

        cache_key = f"{config.through_model.__name__}_{config.source_field}_{config.target_field}"

        if cache_key not in self.through_model_source_target_cache:
            self.through_model_source_target_cache[cache_key] = LRU(config.lru_cache_size)

        if all(obj_id in self.through_model_source_target_cache[cache_key] for obj_id in obj_ids):
            return self.through_model_source_target_cache[cache_key]

        unseen_ids = set(obj_ids) - set(self.through_model_source_target_cache[cache_key].keys())
        through_objects = config.through_model.objects.filter(**{f"{config.source_field}__in": unseen_ids}).values_list(
            config.source_field, config.target_field
        )
        mapping = self.through_model_source_target_cache[cache_key]

        for source_id, target_id in through_objects:
            if source_id not in mapping:
                mapping[source_id] = []
            mapping[source_id].append(target_id)

        self.through_model_source_target_cache[cache_key].update(mapping)
        return mapping

    def process_chunk(self, objects: list[models.Model]) -> None:
        # find all the objects we need to have to process this chunk
        need_objects: dict[type[models.Model], set[int]] = defaultdict(set)
        obj_ids = [obj.id for obj in objects]

        for config in self.memoized_objects_configs.values():
            if config.is_many_to_many:
                related_ids = self._get_m2m_related_ids(obj_ids, config)
                for target_ids in related_ids.values():
                    need_objects[config.model].update(target_ids)
            else:
                for obj in objects:
                    for attribute in config.attributes:
                        if pk := dotted_getattr(obj, f"{attribute}_id"):
                            need_objects[config.model].add(pk)

        # figure out which objects we need to fetch (not already memoized)
        need_to_prefetch: dict[type[models.Model], set[int]] = {}
        for cls, need_ids in need_objects.items():
            need_ids = need_ids - set(self.memoized_objects[cls].keys())
            if need_ids:
                need_to_prefetch[cls] = need_ids

        # prefetch the new objects which are needed
        for cls, need_ids in need_to_prefetch.items():
            new_objects = self.memoized_objects_configs[cls].get_queryset().in_bulk(need_ids)
            # We need to temporarily increase the LRU limit, so the objects that are there do not get cleared
            # because we already rely on them being there
            self.memoized_objects[cls].set_size(self.memoized_objects[cls].get_size() + len(new_objects))
            self.memoized_objects[cls].update(new_objects)

        # assign the attributes on the chunk now we have everything loaded
        for obj in objects:
            for config in self.memoized_objects_configs.values():
                if config.is_many_to_many:
                    self._assign_attributes_from_cache_m2m(config, obj)
                else:
                    self._assign_attributes_from_cache_foreign_key(config, obj)

        # set the correct size for the LRU cache (as we temporarily increased the size before)
        for cls, config in self.memoized_objects_configs.items():
            self.memoized_objects[cls].set_size(config.lru_cache_size)

    def _assign_attributes_from_cache_m2m(self, config: MemoizedPrefetchConfig, obj: models.Model) -> None:
        cache_key = f"{config.through_model.__name__}_{config.source_field}_{config.target_field}"
        related_ids = self.through_model_source_target_cache[cache_key].get(obj.id, [])
        related_objects = [
            self.memoized_objects[config.model][pk] for pk in related_ids if pk in self.memoized_objects[config.model]
        ]
        for attribute in config.attributes:
            # Set in django's internal prefetched objects cache
            # can't use .set as that will cause a lot more queries
            if hasattr(obj, "_prefetched_objects_cache") and attribute in obj._prefetched_objects_cache:
                existing_cache = obj._prefetched_objects_cache[attribute]

                existing_ids = {existing.id for existing in existing_cache}
                for related_obj in related_objects:
                    if related_obj.id not in existing_ids:
                        existing_cache.add(related_obj)
            else:
                if not hasattr(obj, "_prefetched_objects_cache"):
                    obj._prefetched_objects_cache = {}
                obj._prefetched_objects_cache[attribute] = set(related_objects)

    def _assign_attributes_from_cache_foreign_key(self, config: MemoizedPrefetchConfig, obj: models.Model) -> None:
        for attribute in config.attributes:
            if not (pk := dotted_getattr(obj, f"{attribute}_id")):
                continue

            value = self.memoized_objects[config.model][pk]

            # If the attribute is nested (for example invoice__subsidiary), we cannot just run
            # setattr(obj, "invoice__subsidiary", value), as that would not set the subsidiary on the
            # obj.invoice, but rather a new property called "invoice__subsidiary" on the object.
            # Instead, we detect the final concrete object in the chain (e.g. obj.invoice if we use the
            # previous example), and set the attribute on that.
            if "__" in attribute or "." in attribute:
                key_to_use = "__" if "__" in attribute else "."
                # will for example be nested_obj="invoice" and nested_attribute="subsidiary"
                nested_obj, nested_attribute = attribute.rsplit(key_to_use, 1)
                setattr(dotted_getattr(obj, nested_obj), nested_attribute, value)
            else:
                setattr(obj, attribute, value)
