"""Committed-artifact gates: the docs must equal what the code actually prints.

cdfi-stress-tester 0.1.0 shipped a hand-transcribed README quickstart whose every
figure was wrong and whose capital-adequacy verdict was reversed, and a demo notebook
that had never been executed and whose cells raised on the library's own API.

Both are now generated artifacts. These tests re-run the generators in --check mode
and fail if the committed docs no longer match a fresh run.
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"


def _check(script_name: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script_name), "--check"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    "script",
    sorted(p.name for p in SCRIPTS.glob("render_*.py")),
)
def test_committed_artifact_matches_fresh_render(script):
    """Every render_*.py generator agrees with what is committed.

    Parametrised over the scripts actually present, so adding a generator adds a
    gate automatically and nothing here hard-codes how many there are.
    """
    result = _check(script)
    assert result.returncode == 0, (
        f"{script} --check failed (exit {result.returncode}).\n"
        f"Regenerate with: python scripts/{script}\n\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def test_at_least_one_generator_is_gated():
    """Guard against the parametrised test silently covering nothing."""
    generators = list(SCRIPTS.glob("render_*.py"))
    assert generators, "no render_*.py generators found in scripts/"


def test_notebook_executes_without_error():
    """Every notebook code cell runs. 0.1.0 shipped six cells that raised."""
    sys.path.insert(0, str(SCRIPTS))
    import json

    from render_notebook import NOTEBOOK, execute

    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    executed = execute(notebook)  # raises RuntimeError naming any failing cell

    code_cells = [c for c in executed["cells"] if c.get("cell_type") == "code"]
    assert code_cells, "notebook contains no code cells to execute"
    assert all(c["execution_count"] is not None for c in code_cells)

    # No cell may record an error output.
    errored = [
        i
        for i, c in enumerate(executed["cells"])
        if any(o.get("output_type") == "error" for o in c.get("outputs", []))
    ]
    assert not errored, f"notebook cells recorded error output: {errored}"

    # Counts derived from the notebook itself, never typed as literals.
    printing = [c for c in code_cells if c["outputs"]]
    assert len(printing) == len(code_cells), (
        f"{len(code_cells) - len(printing)} of {len(code_cells)} code cells produced "
        "no output; every cell in this demo is expected to print something"
    )


def test_readme_quickstart_output_is_not_hand_written():
    """The README's generated region must carry its do-not-edit marker."""
    sys.path.insert(0, str(SCRIPTS))
    from render_readme_block import BEGIN_MARK, END_MARK, split_readme

    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    _, region, _ = split_readme(text)
    assert region.startswith(BEGIN_MARK)
    assert region.endswith(END_MARK)
    assert "Regenerate: python scripts/render_readme_block.py" in region
