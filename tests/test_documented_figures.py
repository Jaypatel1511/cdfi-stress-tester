"""Gates on every measured figure a document hand-copies.

0.1.0's defect was a README reporting numbers the engine never produced. 0.2.0
fixed the README *quickstart* by generating it -- but the CHANGELOG's "What the
code actually printed" table and README "Known limitations" item 3 still
hand-transcribe measured figures that nothing re-derived. Before this file,
falsifying the CHANGELOG's headline Expected Loss to $1,111,111 left the suite
green, and so did falsifying every figure in README limitation 3.

That gap matters most on the REMEDIATION path. ``render_readme_block.py`` without
``--check`` rewrites README in place, so the natural response to a red golden
gate silently refreshes the generated region while leaving these hand-copied
duplicates stale -- which is exactly the 0.1.0 defect: two documents in one repo
reporting different numbers for the same run. These tests make the duplicates
fail together with the artifact, so a numpy stream move cannot be papered over
by a re-render.
"""
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
CHANGELOG = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO_ROOT))

from cdfistress import (  # noqa: E402
    MonteCarloEngine,
    create_recession_scenario,
    default_correlations,
    from_standard,
    generate_sample_portfolio,
)


def _squash(text: str) -> str:
    """Drop all whitespace, so `$      8,843,297` matches `$8,843,297`."""
    return re.sub(r"\s+", "", text)


@pytest.fixture(scope="module")
def fresh_quickstart_output():
    """stdout of a live run of the README's own quickstart snippet."""
    from render_readme_block import run_quickstart

    return run_quickstart()


@pytest.fixture(scope="module")
def documented_portfolio():
    """The sample portfolio the docs measure, parsed from the quickstart source."""
    from render_readme_block import QUICKSTART_SOURCE

    match = re.search(
        r"generate_sample_portfolio\(n=(\d+),\s*seed=(\d+)\)", QUICKSTART_SOURCE
    )
    assert match, "could not parse the sample portfolio out of QUICKSTART_SOURCE"
    return generate_sample_portfolio(n=int(match.group(1)), seed=int(match.group(2)))


class TestChangelogHeadlineFigures:
    """The 0.2.0 'What the code actually printed' column must still be true."""

    def _actual_column(self):
        section = CHANGELOG.split(
            "### Fixed - the 0.1.0 README reported numbers the code never produced", 1
        )[1].split("\n### ", 1)[0]
        rows = [ln for ln in section.splitlines() if ln.strip().startswith("|")]
        assert rows, "could not find the comparison table in CHANGELOG 0.2.0"
        values = []
        for row in rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) != 3 or set(cells[0]) <= set("- "):
                continue  # separator row
            if cells[2].lower().startswith("what the code"):
                continue  # header row
            values.append(cells[2].strip("*").strip())
        return values

    def test_the_table_was_actually_parsed(self):
        values = self._actual_column()
        assert len(values) >= 6, f"only parsed {values}; the gate would cover nothing"

    def test_every_claimed_figure_appears_in_a_fresh_run(self, fresh_quickstart_output):
        """Each figure must appear in stdout of a live run of the same snippet.

        Compared against a FRESH render, not the committed README, so that
        re-rendering the README cannot on its own turn this green again.
        """
        rendered = _squash(fresh_quickstart_output)
        missing = [v for v in self._actual_column() if _squash(v) not in rendered]
        assert not missing, (
            f"CHANGELOG claims figures the code does not print: {missing}\n"
            "If a numpy upgrade moved the stream, re-render README AND update "
            "these CHANGELOG figures in the same commit.\n"
            f"--- actual output ---\n{fresh_quickstart_output}"
        )

    def test_the_reversed_verdict_is_recorded_correctly(self, fresh_quickstart_output):
        """0.1.0 said ADEQUATE where the code says INSUFFICIENT."""
        assert "STATUS: INSUFFICIENT" in fresh_quickstart_output
        assert "**INSUFFICIENT**" in CHANGELOG


class TestCorrelationExperimentFigures:
    """README limitation 3 and the CHANGELOG both hand-copy this experiment."""

    @staticmethod
    def _means_and_sd(loans, n_seeds, n_iterations):
        scenario = from_standard("2008_recession")
        matrices = {
            "default": default_correlations(),
            "identity": np.eye(3),
            "all_099": np.full((3, 3), 0.99) + np.diag([0.01] * 3),
        }
        means, sds = {}, {}
        for label, matrix in matrices.items():
            engine = MonteCarloEngine(
                loans=loans, available_capital=5_000_000, correlation_matrix=matrix
            )
            els = [
                engine.run_simulation(scenario, n_iterations=n_iterations, seed=s).expected_loss
                for s in range(n_seeds)
            ]
            means[label] = float(np.mean(els))
            sds[label] = float(np.std(els, ddof=0))
        return means, sds

    @staticmethod
    def _params(text, pattern):
        match = re.search(pattern, text)
        assert match, f"could not parse the experiment parameters from {pattern!r}"
        return int(match.group(1)), int(match.group(2).replace(",", ""))

    def test_readme_limitation_3_reproduces(self, documented_portfolio):
        para = README.split("3. **Consequently `correlation_matrix`", 1)[1].split("\n\n", 1)[0]
        n_seeds, n_iterations = self._params(para, r"(\d+) seeds at ([\d,]+) iterations")
        means, sds = self._means_and_sd(documented_portfolio, n_seeds, n_iterations)

        for label in ("default", "identity", "all_099"):
            figure = "${:,.0f}".format(means[label])
            assert figure in para, (
                f"README limitation 3 does not state {figure} for the {label} matrix.\n"
                f"Measured now: {means}\n--- paragraph ---\n{para}"
            )

    def test_changelog_correlation_figures_reproduce(self, documented_portfolio):
        section = CHANGELOG.split("### Documented, not changed", 1)[1].split("\n### ", 1)[0]
        n_seeds, n_iterations = self._params(section, r"over (\d+) seeds x ([\d,]+) iterations")
        means, _ = self._means_and_sd(documented_portfolio, n_seeds, n_iterations)

        for label in ("default", "identity", "all_099"):
            figure = "${:,.0f}".format(means[label])
            assert figure in section, (
                f"CHANGELOG does not state {figure} for the {label} matrix. "
                f"Measured now: {means}"
            )

    def test_the_two_documents_state_the_same_experiment(self):
        """README limitation 3 and the CHANGELOG must not diverge from each other."""
        para = README.split("3. **Consequently `correlation_matrix`", 1)[1].split("\n\n", 1)[0]
        section = CHANGELOG.split("### Documented, not changed", 1)[1].split("\n### ", 1)[0]
        readme_figures = set(re.findall(r"\$[\d,]{7,}", para))
        changelog_figures = set(re.findall(r"\$[\d,]{7,}", section))
        assert readme_figures, "no figures parsed from README limitation 3"
        assert readme_figures == changelog_figures, (
            f"README states {sorted(readme_figures)} but CHANGELOG states "
            f"{sorted(changelog_figures)} for the same experiment"
        )

    def test_the_quoted_across_seed_dispersion_is_real(self, documented_portfolio):
        """The '~$54,000' spread claim must be within range of the measured sd.

        Tolerance rather than an exact match: the document rounds to the nearest
        thousand and does not state its ddof convention. Wide enough to survive
        rounding, narrow enough that falsifying the figure goes red.
        """
        para = README.split("3. **Consequently `correlation_matrix`", 1)[1].split("\n\n", 1)[0]
        n_seeds, n_iterations = self._params(para, r"(\d+) seeds at ([\d,]+) iterations")
        stated = re.search(r"~\$([\d,]+) across-seed standard deviation", para)
        assert stated, f"README limitation 3 states no across-seed dispersion:\n{para}"
        claimed = float(stated.group(1).replace(",", ""))
        _, sds = self._means_and_sd(documented_portfolio, n_seeds, n_iterations)
        measured = sds["default"]
        assert 0.8 * measured <= claimed <= 1.2 * measured, (
            f"README claims ~${claimed:,.0f} across-seed sd; measured "
            f"${measured:,.0f} (all matrices: {sds})"
        )

    def test_the_spread_claim_holds(self, documented_portfolio):
        """'a spread well inside the across-seed standard deviation' must be true."""
        para = README.split("3. **Consequently `correlation_matrix`", 1)[1].split("\n\n", 1)[0]
        n_seeds, n_iterations = self._params(para, r"(\d+) seeds at ([\d,]+) iterations")
        means, sds = self._means_and_sd(documented_portfolio, n_seeds, n_iterations)
        spread = max(means.values()) - min(means.values())
        assert spread < sds["default"], (
            f"the correlation-matrix spread (${spread:,.0f}) is no longer inside the "
            f"across-seed sd (${sds['default']:,.0f}); README limitation 3 says it is"
        )


class TestRemovedSectorScenarioFigure:
    """The CHANGELOG's byte-identical-loss figure for the removed constructor."""

    def test_the_quoted_expected_loss_reproduces(self, documented_portfolio):
        section = CHANGELOG.split("### Removed - `create_sector_specific_scenario`", 1)[1]
        section = section.split("\n### ", 1)[0]
        match = re.search(r"\$([\d,]+\.\d{2}) at `seed=(\d+)`, `n_iterations=(\d+)`", section)
        assert match, f"could not parse the quoted figure from:\n{section}"
        claimed = float(match.group(1).replace(",", ""))
        seed, iterations = int(match.group(2)), int(match.group(3))

        # The removed constructor's own defaults, from 35e0ed0:
        # noi -0.30, rate +0.005, property -0.35, multiplier 2.5, moderate.
        engine = MonteCarloEngine(loans=documented_portfolio, available_capital=5_000_000)
        scenarios = [
            create_recession_scenario(
                noi_shock=-0.30,
                rate_shock=0.005,
                property_value_shock=-0.35,
                default_rate_multiplier=2.5,
                name=f"{sector.title()} Sector Stress",
                severity="moderate",
            )
            for sector in ("small_business", "commercial_real_estate")
        ]
        losses = [
            engine.run_simulation(s, n_iterations=iterations, seed=seed).expected_loss
            for s in scenarios
        ]
        # Compared as the formatted string, to the cent. An `approx(abs=0.01)`
        # tolerance here silently swallowed a falsification of the last digit.
        assert "{:,.2f}".format(losses[0]) == match.group(1), (
            f"CHANGELOG claims ${claimed:,.2f}; measured ${losses[0]:,.2f}"
        )
        assert losses[0] == losses[1], (
            "the two sector labels no longer produce byte-identical losses, which "
            "is the claim the CHANGELOG rests the removal on"
        )


class TestProseThatNamesArtifacts:
    """Small prose claims that were simply wrong, and now have gates."""

    def test_script_docstrings_only_name_test_files_that_exist(self):
        """render_readme_block.py named tests/test_readme_artifact.py, which never existed."""
        offenders = []
        for script in sorted(SCRIPTS.glob("*.py")):
            text = script.read_text(encoding="utf-8")
            for referenced in re.findall(r"\b(tests/[A-Za-z0-9_./-]+\.py)\b", text):
                if not (REPO_ROOT / referenced).is_file():
                    offenders.append(f"{script.name} -> {referenced}")
        assert not offenders, f"script docstrings name test files that do not exist: {offenders}"

    def test_docs_only_name_scripts_that_exist(self):
        offenders = []
        for doc in (REPO_ROOT / "README.md", REPO_ROOT / "CHANGELOG.md"):
            text = doc.read_text(encoding="utf-8")
            for referenced in re.findall(r"\b(scripts/[A-Za-z0-9_./-]+\.py)\b", text):
                if not (REPO_ROOT / referenced).is_file():
                    offenders.append(f"{doc.name} -> {referenced}")
        assert not offenders, f"docs name scripts that do not exist: {offenders}"

    def test_render_notebook_docstring_states_the_real_cell_count(self):
        """The docstring said 'ten code cells'; the notebook has eleven."""
        import json

        from render_notebook import NOTEBOOK

        notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        actual = len([c for c in notebook["cells"] if c.get("cell_type") == "code"])

        words = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
            "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
        }
        docstring = (SCRIPTS / "render_notebook.py").read_text(encoding="utf-8")
        match = re.search(r"of its (\w+) code\s*\n?cells", docstring)
        assert match, "render_notebook.py no longer states a code-cell count"
        stated = words.get(match.group(1).lower())
        assert stated is not None, f"unrecognised number word {match.group(1)!r}"
        assert stated == actual, (
            f"render_notebook.py says {match.group(1)} ({stated}) code cells; "
            f"the notebook has {actual}"
        )

    def test_changelog_agrees_with_the_notebook_cell_count(self):
        import json

        from render_notebook import NOTEBOOK

        notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        actual = len([c for c in notebook["cells"] if c.get("cell_type") == "code"])
        match = re.search(r"(\d+) of its (\d+) code cells raised", CHANGELOG)
        assert match, "CHANGELOG no longer states the notebook cell count"
        assert int(match.group(2)) == actual, (
            f"CHANGELOG says {match.group(2)} code cells; notebook has {actual}"
        )


class TestLoadBearingSafetyDocstring:
    """This warning could be replaced by its own negation with the suite green."""

    def test_recession_scenario_warns_that_shocks_hit_every_loan(self):
        from cdfistress.scenarios.builder import create_recession_scenario as fn

        doc = " ".join((fn.__doc__ or "").split())
        assert "All shocks are applied to EVERY loan in the portfolio." in doc, (
            "create_recession_scenario lost its load-bearing warning. A caller who "
            "believes a named scenario is confined to one segment will under-report "
            "portfolio-wide loss."
        )
        assert "do not use ``name`` to imply that a scenario is confined" in doc

    def test_the_docstring_does_not_claim_a_missing_mechanism(self):
        """The old wording said the engine 'has no mechanism' -- that was false.

        The engine already resolves sector per loan; what is absent is calibration.
        A future session that reads 'no mechanism' will scope an engine rewrite it
        does not need, so the false wording must not come back.
        """
        from cdfistress.scenarios.builder import create_recession_scenario as fn

        doc = " ".join((fn.__doc__ or "").split())
        assert "has no mechanism" not in doc, (
            "docstring claims the engine has no per-segment mechanism. It does: "
            "_compute_loss_distribution resolves SECTOR_DEFAULT_RATES per loan. "
            "What is missing is calibration."
        )
        assert "CALIBRATION, not mechanism" in doc

    def test_the_readme_limitation_rests_on_calibration_not_mechanism(self):
        limitation = README.split("1. **Scenario shocks are portfolio-wide", 1)[1]
        limitation = limitation.split("\n2. ", 1)[0]
        assert "calibration, not mechanism" in limitation.lower()
        assert "no mechanism" not in limitation.lower(), (
            "README limitation 1 still asserts the engine lacks the mechanism"
        )


class TestSectorDifferentiationClaim:
    """The claim the 0.2.0 wording change rests on is itself a measured figure."""

    def test_the_quoted_sector_and_pd_counts_are_real(self, documented_portfolio):
        from cdfistress.data.schema import SECTOR_DEFAULT_RATES

        words = {"three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
        match = re.search(
            r"spans (\w+) sectors and (\w+)\s*\n?\s*distinct PDs", CHANGELOG
        )
        assert match, "CHANGELOG no longer states the sector/PD counts"
        stated_sectors = words[match.group(1).lower()]
        stated_pds = words[match.group(2).lower()]

        engine = MonteCarloEngine(loans=documented_portfolio, available_capital=5_000_000)
        pds = engine.default_probabilities(from_standard("2008_recession"))
        actual_sectors = len({loan.sector for loan in documented_portfolio})
        actual_pds = len(set(pds.values()))

        assert stated_sectors == actual_sectors, (
            f"CHANGELOG says {stated_sectors} sectors; portfolio has {actual_sectors}"
        )
        assert stated_pds == actual_pds, (
            f"CHANGELOG says {stated_pds} distinct PDs; measured {actual_pds}"
        )
        assert actual_pds > 1, "the per-loan sector mechanism the wording rests on is gone"
        # Fewer PDs than sectors is expected: office and mixed_use share a rate.
        assert actual_pds <= actual_sectors
        assert actual_pds == len(
            {SECTOR_DEFAULT_RATES.get(l.sector, 0.035) for l in documented_portfolio}
        )


class TestChangelogTestCount:
    """The changelog states a test count. That is a measured figure too."""

    def test_the_stated_test_count_matches_what_pytest_collects(self):
        """0.2.0's changelog said 93 and was right; keeping it right is the point.

        Collected in a subprocess rather than counted from this session, so the
        figure is what a reader reproduces by running the suite.
        """
        import subprocess

        result = subprocess.run(
            [
                sys.executable, "-m", "pytest", "--collect-only", "-q",
                "-p", "no:cacheprovider", str(REPO_ROOT / "tests"),
            ],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
        )
        assert result.returncode == 0, f"collection failed:\n{result.stdout}\n{result.stderr}"
        collected = re.search(r"(\d+) tests? collected", result.stdout)
        assert collected, f"could not parse a collected count from:\n{result.stdout[-2000:]}"
        actual = int(collected.group(1))

        stated = re.search(r"64 tests in 0\.1\.0 -> (\d+) in 0\.2\.0", CHANGELOG)
        assert stated, "CHANGELOG no longer states a test count for 0.2.0"
        assert int(stated.group(1)) == actual, (
            f"CHANGELOG says {stated.group(1)} tests in 0.2.0; pytest collects {actual}"
        )
