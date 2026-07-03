# Project Rules Index

This directory is the source of truth for project rules, boundaries, and task-specific conventions.

Agents must use this file as a routing index only. Read the smallest relevant rule entry for the current task, then follow that entry's own disclosure path. Do not load every rule file at once.

## Routing

### Directory Structure

Use `directory-structure/README.md` when the task involves file placement, repository layout, directory ownership, or read/write boundaries.

### Coding Specification

Use `coding-specification/README.md` when the task involves writing code, modifying code, running commands, using Python or `uv`, or checking operation safety boundaries.

### Subagent Invocation

Use `subagent-invocation/README.md` when the task involves calling other OpenCode agents, choosing an agent path, or configuring subagent invocation permissions.
