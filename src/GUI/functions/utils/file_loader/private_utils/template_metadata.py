def split_front_matter(content: str) -> tuple[dict[str, str], str]:
    """
    Extract a simple YAML front matter block from the beginning of a markdown file.
    Flat key/value pairs are returned when available. The splitter remains
    intentionally permissive because report and uploaded Markdown metadata is
    preserved rather than used as a document-type gate.
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
