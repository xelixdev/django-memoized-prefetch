from __future__ import annotations

__all__ = ["dotted_getattr"]


def dotted_getattr(obj, name):
    """
    On an object, performs a recursive getattr, by attribute names split by either __ or .

    For example, both of these will work identically.

    >> dotted_getattr(obj, 'child.fk_id')
    >> dotted_getattr(obj, 'child__fk_id')
    """
    key_to_use = "__" if "__" in name else "."
    keys = name.split(key_to_use)

    for i, key in enumerate(keys):
        # if not last one check the related object is actually set
        if i != len(keys) - 1 and getattr(obj, f"{key}_id") is None:
            return None

        obj = getattr(obj, key)

    return obj
