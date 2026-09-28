"""agent-team: fire a bounded team of agents into an isolated subtree to produce one deliverable.

Three levels (see README):
  roles/    -- the personalities (reusable prompt files): pi, worker, verifier, code-reviewer, ...
  recipes/  -- job types: cast roles into a team + choreography + deliverable
  a job     -- one run of a recipe in jobs/<id>/, staffed by you or the PI, that you then
               resume / freeze / abandon.

Pure standard library. Backends (claude, codex, mock) are swappable per job.
"""

import os

HOME = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # repo root (the tool)
ROLES_DIR = os.path.join(HOME, "roles")
RECIPES_DIR = os.path.join(HOME, "recipes")
TEMPLATES_DIR = os.path.join(HOME, "templates")

# Per-project overrides (agent-team-plantilla): a project may carry its own cast, job types and
# PI policy in <project>/.agent-team/{roles,recipes,policy.json}. They are looked up first, so a
# project can add a role or tighten the policy without touching the shared tool.
PROJECT_CONFIG = ".agent-team"


def project_config_dir() -> str:
    root = os.environ.get("AGENT_TEAM_PROJECT", os.getcwd())
    return os.path.join(root, PROJECT_CONFIG)


def lookup_dirs(sub: str) -> list:
    """Directories to search for ``sub`` ("roles" / "recipes"), project first, tool last."""
    return [os.path.join(project_config_dir(), sub), os.path.join(HOME, sub)]


def find_file(sub: str, filename: str):
    """First existing ``sub/filename`` in lookup order, or None."""
    for d in lookup_dirs(sub):
        path = os.path.join(d, filename)
        if os.path.exists(path):
            return path
    return None


def list_names(sub: str, ext: str) -> list:
    names = set()
    for d in lookup_dirs(sub):
        if os.path.isdir(d):
            names.update(f[:-len(ext)] for f in os.listdir(d) if f.endswith(ext))
    return sorted(names)

__version__ = "0.1.0"
