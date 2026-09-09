"""Gates on what actually ships: dependencies, the sdist, the licence, metadata.

Three defects motivate this file, all of which the 0.2.0 branch shipped green:

* ``pandas`` was declared as a runtime dependency in ``pyproject.toml``, in
  ``setup.py`` and twice in the README, and was never imported anywhere in the
  package.  Every installer paid for it; nothing used it.
* The sdist shipped a test suite that could not run.  ``tests/conftest.py``,
  ``scripts/``, ``examples/``, ``.github/`` and ``CHANGELOG.md`` were all absent,
  so from the tarball root the suite gave ``6 failed, 50 passed, 1 skipped,
  35 errors`` -- and the committed-artifact gate parametrised over
  ``SCRIPTS.glob("render_*.py")`` found ZERO scripts and silently skipped.
  This is the same defect class the portfolio declared fully closed on
  2026-09-05; it reopened here because CI never built a distribution.
* No ``LICENSE`` file existed anywhere -- not in the repo, the wheel or the
  sdist -- while MIT was asserted in the README badge, the README footer,
  ``pyproject.toml`` and ``setup.py``.

Note for 3.9: ``tomllib`` is 3.11+, and CI's floor is 3.9, so pyproject is read
with regexes rather than a TOML parser.
"""
import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE = REPO_ROOT / "cdfistress"
PYPROJECT = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
SETUP_PY = (REPO_ROOT / "setup.py").read_text(encoding="utf-8")

# Distribution names whose import name differs from the normalised project name.
# An unmapped mismatch produces a false RED, never a false green -- which is the
# correct direction for a gate whose whole job is catching a phantom dependency.
_IMPORT_ALIASES = {
    "pillow": "PIL",
    "pyyaml": "yaml",
    "scikit-learn": "sklearn",
    "beautifulsoup4": "bs4",
    "python-dateutil": "dateutil",
}


def _array(text: str, key: str):
    """Return the quoted string entries of a single-level TOML/Python array."""
    match = re.search(rf"^\s*{key}\s*=\s*\[(.*?)\]", text, re.S | re.M)
    if match is None:
        return None
    return re.findall(r'"([^"]+)"', match.group(1))


def _dist_name(requirement: str) -> str:
    return re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement).group(1)


def _import_name(dist: str) -> str:
    return _IMPORT_ALIASES.get(dist.lower(), dist.lower().replace("-", "_").replace(".", "_"))


def _modules_imported_by_the_package():
    """Top-level module names imported anywhere under cdfistress/."""
    found = set()
    sources = sorted(PACKAGE.rglob("*.py"))
    assert sources, f"no package sources found under {PACKAGE}"
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    found.add(node.module.split(".")[0])
    return found


class TestDeclaredDependenciesAreReal:
    """Every declared runtime dependency must actually be imported."""

    def test_pyproject_dependencies_are_imported_by_the_package(self):
        declared = _array(PYPROJECT, "dependencies")
        assert declared, "pyproject.toml declares no dependencies array"
        imported = _modules_imported_by_the_package()
        phantom = [
            d for d in declared if _import_name(_dist_name(d)) not in imported
        ]
        assert not phantom, (
            f"declared in pyproject.toml but never imported under {PACKAGE.name}/: "
            f"{phantom}. Either import it or drop it -- 0.2.0 shipped `pandas` "
            f"this way. Package imports: {sorted(imported)}"
        )

    def test_setup_py_install_requires_are_imported_by_the_package(self):
        declared = _array(SETUP_PY, "install_requires")
        assert declared, "setup.py declares no install_requires array"
        imported = _modules_imported_by_the_package()
        phantom = [
            d for d in declared if _import_name(_dist_name(d)) not in imported
        ]
        assert not phantom, (
            f"declared in setup.py but never imported: {phantom}"
        )

    def test_both_declaration_sites_agree(self):
        """pyproject's [project] wins over setup.py, so a drift is invisible."""
        pyproject = sorted(_array(PYPROJECT, "dependencies"))
        setup = sorted(_array(SETUP_PY, "install_requires"))
        assert pyproject == setup, (
            f"pyproject.toml declares {pyproject} but setup.py declares {setup}. "
            "pyproject's [project] table silently overrides setup.py, so the "
            "setup.py list would never be exercised."
        )

    def test_the_readme_does_not_advertise_an_undeclared_dependency(self):
        """The README named pandas twice while nothing imported it."""
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        declared = {_dist_name(d).lower() for d in _array(PYPROJECT, "dependencies")}
        # Runtime stacks a reader could reasonably believe are required.
        candidates = ["pandas", "scipy", "numpy", "polars", "statsmodels", "matplotlib"]
        advertised = {c for c in candidates if re.search(rf"\b{c}\b", readme, re.I)}
        overclaimed = sorted(advertised - declared)
        assert not overclaimed, (
            f"README names {overclaimed} as if required, but pyproject declares "
            f"{sorted(declared)}"
        )


class TestLicence:
    """MIT was asserted in four places with no LICENSE file anywhere."""

    def test_license_file_exists(self):
        assert (REPO_ROOT / "LICENSE").is_file(), (
            "no LICENSE file. MIT is asserted in the README badge, the README "
            "footer, pyproject.toml and setup.py; counsel at a regulated "
            "institution checks for the file, not the badge."
        )

    def test_license_is_mit_and_names_a_holder(self):
        text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
        assert "MIT License" in text
        assert "Permission is hereby granted, free of charge" in text
        assert re.search(r"Copyright \(c\) \d{4} \S", text), (
            "LICENSE must carry a `Copyright (c) YEAR Holder` line"
        )

    def test_declared_license_agrees_with_the_license_file(self):
        assert re.search(r'license\s*=\s*\{[^}]*"MIT"', PYPROJECT), PYPROJECT
        assert 'license="MIT"' in SETUP_PY


class TestDistributionMetadata:
    """Both 0.1.0 and 0.2.0 shipped wheels with zero Classifier lines."""

    def test_pyproject_declares_classifiers(self):
        classifiers = _array(PYPROJECT, "classifiers")
        assert classifiers, (
            "pyproject.toml [project] declares no classifiers. It overrides "
            "setup.py's, so the wheel METADATA ships with no Classifier line."
        )

    def test_classifiers_cover_every_interpreter_in_the_ci_matrix(self):
        classifiers = _array(PYPROJECT, "classifiers")
        declared = {
            c.rsplit("::", 1)[1].strip()
            for c in classifiers
            if c.startswith("Programming Language :: Python :: ") and "." in c
        }
        workflow = "\n".join(
            p.read_text(encoding="utf-8")
            for p in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
        )
        matrix = set(
            re.findall(r'"(\d+\.\d+)"', re.search(r"python-version:\s*\[([^\]]*)\]", workflow).group(1))
        )
        assert matrix, "no python-version matrix found"
        assert matrix <= declared, (
            f"CI tests {sorted(matrix)} but classifiers declare {sorted(declared)}"
        )

    def test_license_classifier_present(self):
        assert "License :: OSI Approved :: MIT License" in _array(PYPROJECT, "classifiers")


class TestSdistShipsARunnableSuite:
    """The 0.2.0 sdist omitted everything the suite needs to run."""

    def test_manifest_exists(self):
        assert (REPO_ROOT / "MANIFEST.in").is_file(), (
            "no MANIFEST.in: setuptools ships only package sources plus a few "
            "defaults, so tests/conftest.py, scripts/, examples/ and .github/ "
            "were all absent from the sdist and 35 tests errored from the tarball."
        )

    def test_manifest_covers_everything_the_shipped_suite_needs(self):
        """Derived from what the suite actually reaches for, not a typed list."""
        manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        required = {
            "tests": r"recursive-include\s+tests\s",
            "scripts": r"recursive-include\s+scripts\s",
            "examples": r"recursive-include\s+examples\s",
            ".github": r"recursive-include\s+\.github\s",
            "CHANGELOG.md": r"include\s+CHANGELOG\.md",
            "LICENSE": r"include\s+LICENSE",
        }
        missing = [name for name, pat in required.items() if not re.search(pat, manifest)]
        assert not missing, (
            f"MANIFEST.in does not ship {missing}. tests/conftest.py supplies every "
            "fixture; scripts/ is what test_committed_artifacts parametrises over "
            "(zero scripts => silent skip); .github/ is what test_ci_workflow reads."
        )

    def test_conftest_is_not_excluded(self):
        """conftest.py is the single file whose absence errored 35 tests."""
        manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        assert not re.search(r"^\s*(exclude|prune|global-exclude).*conftest", manifest, re.M | re.I)
        assert (REPO_ROOT / "tests" / "conftest.py").is_file()


class TestCiBuildsADistribution:
    """CI only ever tested the working tree, so it could not see the sdist gap."""

    def _workflow_text(self):
        return "\n".join(
            p.read_text(encoding="utf-8")
            for p in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
        )

    def test_a_job_builds_the_distributions(self):
        text = self._workflow_text()
        assert re.search(r"python -m build", text), (
            "no CI step builds a distribution, so no CI step can catch a broken sdist"
        )

    def test_a_job_extracts_the_tarball_and_runs_the_shipped_suite(self):
        text = self._workflow_text()
        assert re.search(r"tar\s+xzf\s+dist/\*\.tar\.gz", text), (
            "CI does not extract the built sdist"
        )
        # The pytest invocation must come after a cd into the extracted root,
        # otherwise it re-tests the working tree and proves nothing. Checked by
        # ordering rather than adjacency so intervening steps stay allowed.
        after_extract = text.split("tar xzf dist/*.tar.gz", 1)[1]
        cd_at = after_extract.find("cd /tmp/sdist-check/")
        pytest_at = after_extract.find("python -m pytest")
        assert cd_at != -1, "CI never changes into the extracted sdist root"
        assert pytest_at != -1, "CI never runs pytest after extracting the sdist"
        assert cd_at < pytest_at, (
            "CI runs pytest before entering the extracted sdist root, so it "
            "re-tests the working tree and proves nothing about the tarball"
        )
