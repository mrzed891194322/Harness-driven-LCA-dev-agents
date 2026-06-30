from pathlib import Path

PLAN_TEMPLATE_KIND = "lca_plan_input"
PLAN_TEMPLATE_VERSION = "1"

REQUIRED_TEMPLATE_METADATA = {
    "template_kind": PLAN_TEMPLATE_KIND,
    "template_version": PLAN_TEMPLATE_VERSION,
}


def split_front_matter(content: str) -> tuple[dict[str, str], str]:
    """
    Extract a simple YAML front matter block from the beginning of a markdown file.
    Only flat key: value pairs are supported because template identity metadata is simple.
    """
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return {}, content

    end_marker = normalized.find("\n---", 4)
    if end_marker == -1:
        return {}, content

    after_marker_idx = end_marker + len("\n---")
    if after_marker_idx < len(normalized) and normalized[after_marker_idx] not in "\n":
        return {}, content

    yaml_text = normalized[4:end_marker]
    body = normalized[after_marker_idx:]
    if body.startswith("\n"):
        body = body[1:]

    metadata = parse_simple_yaml(yaml_text)
    return metadata, body


def parse_simple_yaml(yaml_text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for raw_line in yaml_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            return {}

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if not key:
            return {}
        metadata[key] = value
    return metadata


def read_template_metadata(filepath: Path) -> dict[str, str]:
    if not filepath.exists():
        return {}
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return {}
    metadata, _ = split_front_matter(content)
    return metadata


def is_supported_plan_template(filepath: Path) -> bool:
    metadata = read_template_metadata(filepath)
    return all(
        metadata.get(key) == value
        for key, value in REQUIRED_TEMPLATE_METADATA.items()
    )
