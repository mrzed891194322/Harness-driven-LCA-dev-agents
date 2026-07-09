def is_in_project_category(category: str | None, project_name: str) -> bool:
    if not category:
        return False
    return category == project_name or category.startswith(project_name + "/")


def collect_entities(client, project_name: str, model_types: list[type]) -> list[tuple[type, object]]:
    entities = []
    for model_type in model_types:
        try:
            descriptors = client.get_descriptors(model_type)
        except Exception as exc:
            print(f"[WARNING] Failed to get {model_type.__name__} descriptors: {exc}")
            continue

        for descriptor in descriptors:
            if is_in_project_category(getattr(descriptor, "category", None), project_name):
                entities.append((model_type, descriptor))
    return entities


def print_entities(entities: list[tuple[type, object]]) -> None:
    for model_type, descriptor in entities:
        category = getattr(descriptor, "category", "")
        print(f"  - {model_type.__name__}: {descriptor.name} | {descriptor.id} | category={category}")


def delete_entities(client, entities: list[tuple[type, object]], model_types: list[type]) -> int:
    deleted_count = 0
    for model_type in model_types:
        current = [item for item in entities if item[0] == model_type]
        if not current:
            continue

        print(f"Deleting {model_type.__name__} entities: {len(current)}")
        for _, descriptor in current:
            try:
                client.delete(descriptor.to_ref())
                deleted_count += 1
                print(f"  [DELETED] {descriptor.name} ({descriptor.id})")
            except Exception as exc:
                print(f"  [ERROR] Failed to delete {descriptor.name} ({descriptor.id}): {exc}")
    return deleted_count
