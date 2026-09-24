"""Exact entity lookup with transport failures preserved."""

from typing import Any
from uuid import UUID

from .protocols import OpenLcaClient


def find_entity(client: OpenLcaClient, model_type, name_or_uuid):
    try:
        UUID(name_or_uuid)
        exact_id = True
    except (ValueError, TypeError, AttributeError):
        exact_id = False
    descriptor_lookup = getattr(client, "get_descriptor", None)
    if not exact_id and callable(descriptor_lookup):
        reference: Any = descriptor_lookup(model_type, name=name_or_uuid)
        return client.get(model_type, reference.id) if reference is not None else None
    try:
        entity = client.get(model_type, name_or_uuid)
    except ValueError:
        if exact_id:
            raise
        entity = None
    if entity is not None or exact_id:
        return entity
    # A transport/RPC failure is never interpreted as permission to scan again.
    finder = getattr(client, "find", None)
    if callable(finder):
        reference = finder(model_type, name_or_uuid)
        return client.get(model_type, reference.id) if reference is not None else None
    for descriptor in list(client.get_descriptors(model_type) or []):
        if descriptor.id == name_or_uuid or descriptor.name == name_or_uuid:
            return client.get(model_type, descriptor.id)
    return None
