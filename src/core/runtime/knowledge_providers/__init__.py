"""Built-in knowledge providers for the generic harness runtime."""

from .local_files import PROVIDER_ID, enrich_local_files, register_local_files

__all__ = ["PROVIDER_ID", "enrich_local_files", "register_local_files"]
