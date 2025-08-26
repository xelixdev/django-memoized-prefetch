from __future__ import annotations

__all__ = ["MemoizedPrefetchConfig"]

import dataclasses

from django.db import models
from django.db.models import QuerySet


@dataclasses.dataclass
class MemoizedPrefetchConfig:
    """
    Parameters for MemoizedPrefetch. Primary parameters are the model and a list of attributes to prefetch.
    For example, if there's an attribute `child` on your object,
    you'd create `MemoizedPrefetchConfig(Child, ["child"])`.

    If you want to do a memoized prefetch for a many-to-many field, you need to set `is_many_to_many=True` and set the
    through_model of the m2m field. source_field should be the field (string) on the m2m through model that links to the
    source model id. target_field should be the field on the m2m through model (string) that links to the target model
    id.

    There's additional parameters for setting the queryset (to add more select or prefetch related, for example), and
    whether all the objects in the database should be prefetched at the start (for example if there
    will ever only be a couple objects in the database, so we can fetch at the start of processing).

    Finally, you can set the LRU cache size - to prevent memory issues, we only keep a certain number of objects in
    the cache, the one most recently used ones. The default cache size is 10000 objects.
    """

    model: type[models.Model]
    attributes: list[str]
    queryset: QuerySet | None = None
    prefetch_all: bool = False
    lru_cache_size: int = 10_000
    is_many_to_many: bool = False
    through_model: type[models.Model] | None = None
    source_field: str | None = None
    target_field: str | None = None

    def __post_init__(self):
        if self.is_many_to_many and (not self.through_model or not self.source_field or not self.target_field):
            msg = "For many-to-many relationships, through_model, source_field, and target_field must be provided"
            raise ValueError(msg)

    def get_queryset(self) -> QuerySet:
        if self.queryset is None:
            queryset = self.model.objects.all()
        else:
            queryset = self.queryset

        if hasattr(queryset, "seal"):  # support for django-seal
            queryset = queryset.seal()

        return queryset
