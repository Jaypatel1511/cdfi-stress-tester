"""Gates on the CI workflow itself.

CI is what enforces the committed-artifact gates on every supported interpreter,
so the workflow's own correctness is worth testing: an unpinned action or a matrix
that has drifted away from `requires-python` would quietly weaken everything else.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"


def _workflows():
    return sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))


def test_a_workflow_exists():
    assert _workflows(), f"no workflow files found under {WORKFLOW_DIR}"


def test_every_action_is_pinned_to_a_commit_sha():
    """A tag can be moved under you; a commit SHA cannot."""
    unpinned = []
    for path in _workflows():
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.search(r"^\s*(?:-\s*)?uses:\s*(\S+)", line)
            if not match:
                continue
            ref = match.group(1)
            if not re.fullmatch(r"[\w.\-]+/[\w.\-/]+@[0-9a-f]{40}", ref):
                unpinned.append(f"{path.name}: {ref}")
    assert not unpinned, f"actions not pinned to a 40-char commit SHA: {unpinned}"


def test_every_pinned_action_records_the_human_readable_version():
    """Each pinned SHA carries a trailing `# vX.Y.Z` so it can be audited."""
    missing = []
    for path in _workflows():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not re.search(r"^\s*(?:-\s*)?uses:\s*\S+@[0-9a-f]{40}", line):
                continue
            if not re.search(r"@[0-9a-f]{40}\s*#\s*v?\d", line):
                missing.append(f"{path.name}: {line.strip()}")
    assert not missing, f"pinned actions without a version comment: {missing}"


def test_matrix_minimum_matches_requires_python():
    """The oldest interpreter CI runs must be the oldest the package claims."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    declared = re.search(r'requires-python\s*=\s*">=\s*([0-9.]+)"', pyproject).group(1)

    versions = set()
    for path in _workflows():
        text = path.read_text(encoding="utf-8")
        block = re.search(r"python-version:\s*\[([^\]]*)\]", text)
        if block:
            versions |= set(re.findall(r'"([0-9.]+)"', block.group(1)))
    assert versions, "no python-version matrix found in any workflow"

    def key(v):
        return tuple(int(part) for part in v.split("."))

    assert min(versions, key=key) == declared, (
        f"CI matrix minimum is {min(versions, key=key)} but pyproject declares "
        f"requires-python >={declared}"
    )


def test_matrix_versions_are_unique_and_contiguous():
    """Derived from the matrix itself -- no literal count is typed here."""
    text = "\n".join(p.read_text(encoding="utf-8") for p in _workflows())
    listed = re.findall(r'"(\d+\.\d+)"', re.search(r"python-version:\s*\[([^\]]*)\]", text).group(1))
    assert len(listed) == len(set(listed)), f"duplicate versions in matrix: {listed}"

    minors = sorted(int(v.split(".")[1]) for v in listed)
    assert minors == list(range(minors[0], minors[0] + len(minors))), (
        f"CI matrix skips an interpreter: {listed}"
    )
