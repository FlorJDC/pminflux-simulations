"""Load role personalities from roles/*.md.

A role is just a prompt file. It defines *who* an agent is (a verifier, a coder, the PI);
recipes decide *how many* and *in what order*. Roles are the portable, shareable cast that
travels with the repo.
"""

from __future__ import annotations

import os

from . import ROLES_DIR, find_file, list_names


def load(role_name: str) -> str:
    path = find_file("roles", f"{role_name}.md")
    if path is None:
        raise FileNotFoundError(f"role {role_name!r} not found in .agent-team/roles/ or {ROLES_DIR}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def available() -> list[str]:
    return list_names("roles", ".md")
