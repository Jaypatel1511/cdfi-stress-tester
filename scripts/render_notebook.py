#!/usr/bin/env python3
"""Execute examples/cdfi_stress_test_demo.ipynb and write its real outputs back in.

WHY THIS EXISTS
---------------
The 0.1.0 demo notebook was committed having never been run. Six of its eleven code
cells raised on import of the library's own API (``loan.commitment_amount``,
``scenario_comparison_table(...).to_string()``, ``tail_loss(..., percentile=99)``
and others). Nothing caught it because nothing executed it.

This renderer executes every code cell in order, exactly as a reader would when
running the notebook from the ``examples/`` directory, and stores the captured
stdout as each cell's output. ``tests/test_committed_artifacts.py`` re-runs it in
``--check`` mode, so a notebook that no longer executes -- or whose committed
outputs no longer match a fresh run -- fails CI.

NUMPY STREAM STABILITY -- READ BEFORE "FIXING" A RED GOLDEN GATE
---------------------------------------------------------------
The committed figures come from ``numpy.random.Generator``.  numpy's own
docstring carries "No Compatibility Guarantee ... the bit stream may change",
and the draws route through LAPACK ``gesdd``, whose singular-vector signs are
not a standardised convention across builds.  The figures were verified
identical on numpy 1.26.4 and 2.2.6, but that is evidence, not a guarantee.

So: if this gate goes RED after a numpy (or BLAS/LAPACK) upgrade and NO source
change, the stream moved.  That is not a bug in the engine and re-rendering
alone is NOT the fix.  Re-render AND update every document that hand-copies
these figures, in the same commit:

  * README.md  -- the generated region (this script rewrites it) AND the
    hand-written "Known limitations" item 3, which this script does NOT own.
  * CHANGELOG.md -- the 0.2.0 "What the code actually printed" table and the
    "Documented, not changed" correlation figures, which are hand-copied.

Running this script WITHOUT ``--check`` rewrites README.md in place.  Doing that
on its own is exactly how 0.1.0's defect returns: two documents in this repo
reporting different numbers for the same run.  ``tests/test_documented_figures.py``
gates the hand-copied duplicates against a fresh render so this cannot pass
silently.

USAGE
-----
    python scripts/render_notebook.py            # execute and write outputs in place
    python scripts/render_notebook.py --check    # exit 1 if stale or if any cell raises
"""
from __future__ import annotations

import argparse
import contextlib
import difflib
import io
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = REPO_ROOT / "examples" / "cdfi_stress_test_demo.ipynb"


def _dump(nb: dict) -> str:
    """Serialise a notebook deterministically. Must match what is committed."""
    return json.dumps(nb, indent=1, ensure_ascii=False) + "\n"


def execute(nb: dict) -> dict:
    """Return a copy of ``nb`` with every code cell executed and its stdout stored.

    Raises RuntimeError naming the offending cell if any cell raises.
    """
    nb = json.loads(json.dumps(nb))  # deep copy
    namespace: dict = {"__name__": "__notebook__"}
    counter = 0
    prev_cwd = os.getcwd()
    prev_path = list(sys.path)
    # Run from examples/ so the notebook's own `sys.path.insert(0, '..')` resolves
    # to the repo root, exactly as it does for a reader.
    os.chdir(NOTEBOOK.parent)
    try:
        for index, cell in enumerate(nb["cells"]):
            if cell.get("cell_type") != "code":
                continue
            counter += 1
            source = "".join(cell["source"])
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    exec(compile(source, f"<cell {index}>", "exec"), namespace)
            except Exception as exc:
                raise RuntimeError(
                    f"notebook cell [{index}] raised "
                    f"{type(exc).__name__}: {exc}\n--- cell source ---\n{source}"
                ) from exc
            text = buf.getvalue()
            cell["execution_count"] = counter
            cell["outputs"] = (
                [
                    {
                        "output_type": "stream",
                        "name": "stdout",
                        "text": text.splitlines(keepends=True),
                    }
                ]
                if text
                else []
            )
    finally:
        os.chdir(prev_cwd)
        sys.path[:] = prev_path
    return nb


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the committed notebook is stale or does not execute",
    )
    args = parser.parse_args()

    committed_text = NOTEBOOK.read_text(encoding="utf-8")
    fresh_text = _dump(execute(json.loads(committed_text)))

    if committed_text == fresh_text:
        print("Notebook outputs are up to date.")
        return 0

    if args.check:
        diff = difflib.unified_diff(
            committed_text.splitlines(keepends=True),
            fresh_text.splitlines(keepends=True),
            fromfile="notebook (committed)",
            tofile="notebook (freshly executed)",
        )
        sys.stdout.writelines(diff)
        print("\nNotebook is STALE. Regenerate: python scripts/render_notebook.py")
        return 1

    NOTEBOOK.write_text(fresh_text, encoding="utf-8")
    print("Notebook outputs regenerated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
