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

import cdfistress  # noqa: E402
from cdfistress import (  # noqa: E402
    STANDARD_SCENARIOS,
    MonteCarloEngine,
    create_recession_scenario,
    default_correlations,
    from_standard,
    generate_sample_portfolio,
)


def _squash(text: str) -> str:
    """Drop all whitespace, so `$      8,843,297` matches `$8,843,297`."""
    return re.sub(r"\s+", "", text)


# --------------------------------------------------------------------------
# Notebook accessors.  Every notebook gate below goes through these, so no gate
# can quietly widen its scope back to "the whole artifact" without editing one
# of them.
# --------------------------------------------------------------------------


def _notebook() -> dict:
    import json

    from render_notebook import NOTEBOOK

    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def _markdown_cells():
    """``[(index, source)]`` for the notebook's markdown cells, in order."""
    return [
        (index, "".join(cell["source"]))
        for index, cell in enumerate(_notebook()["cells"])
        if cell.get("cell_type") == "markdown"
    ]


def _code_cells():
    return [
        "".join(cell["source"])
        for cell in _notebook()["cells"]
        if cell.get("cell_type") == "code"
    ]


def _flat(text: str) -> str:
    """Collapse whitespace so a claim that wrapped across lines still matches."""
    return " ".join(text.split())


def _markdown_cell_containing(heading: str):
    """The ONE markdown cell whose source contains ``heading``.

    Scoped the way ``tests/test_api_surface.py`` scopes to ``## API Reference``,
    and for the identical reason. The gate this replaces joined every markdown
    cell into one string and substring-searched the union, so it did not check
    the section it named at all: rewriting the scenario section to
    "Sector targeting is simply unsupported today." and parking the phrase
    "calibration, not mechanism. SECTOR_DEFAULT_RATES." in the title cell shipped
    161 passed.
    """
    matches = [(index, source) for index, source in _markdown_cells() if heading in source]
    assert len(matches) == 1, (
        f"expected exactly one markdown cell containing {heading!r}, found "
        f"{[i for i, _ in matches]}; the scoped gates below would cover the "
        "wrong cell or none at all"
    )
    return matches[0]


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

    def test_the_changelogs_word_form_cell_count_agrees_too(self):
        """The digit form was gated; the word form 40 lines away was not.

        `**eleven** code cells` -> `**twelve**` shipped 161 passed, in the very
        bullet that records finding a prose claim that named a file which never
        existed.
        """
        import json

        from render_notebook import NOTEBOOK

        notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        actual = len([c for c in notebook["cells"] if c.get("cell_type") == "code"])
        found = re.findall(r"\*\*(\w+)\*\* code cells", CHANGELOG)
        assert found, "CHANGELOG no longer states the cell count in word form"
        for word in found:
            stated = _WORD_NUMBERS.get(word.lower())
            assert stated is not None, f"unrecognised number word {word!r}"
            assert stated == actual, (
                f"CHANGELOG says **{word}** ({stated}) code cells; "
                f"the notebook has {actual}"
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


# Wordings that assert the engine LACKS a per-segment mechanism.  It does not:
# both ``_compute_loss_distribution`` and ``default_probabilities`` resolve
# ``SECTOR_DEFAULT_RATES.get(loan.sector, ...)`` per loan, and the sample
# portfolio already yields several distinct PDs.  What is absent is CALIBRATION.
#
# WHAT THIS SWEEP DOES AND DOES NOT DO -- read before trusting it.
#
# It matches an ENUMERATED FAMILY OF DENIAL SHAPES.  It does not understand
# meaning, and it cannot catch an arbitrary paraphrase of a false claim.  Every
# one of these shipped 161 passed against the four-pattern version this replaces:
#
#     "The engine cannot stress one sector or geography and not another."
#     "There is no way to stress one sector or geography and not another."
#     "The engine is unable to target a single sector or geography."
#     "The engine has no capability for stressing one sector or geography."
#     "The engine does not resolve sector per loan."
#
# All five are covered now, and so are the four original wordings.  A sixth
# phrasing nobody listed still walks through, and no list of regexes will fix
# that.  The POSITIVE gates -- ``TestNoTrackedArtifactDeniesTheMechanism
# .test_the_notebook_scenario_section_states_calibration_not_mechanism`` and the
# README/docstring gates in ``TestLoadBearingSafetyDocstring`` -- are what
# guarantee the CORRECT statement is present; this sweep only removes a set of
# known-wrong ones.  Say it that way in any document that describes it.
#
# Each entry pairs a pattern with a PROBE it must match.  The previous guard was
# ``assert any(...)`` over one shipped sentence, so only patterns 1 and 2 were
# ever exercised: replacing pattern 1, 3 or 4 with ``ZZZZQQQ_NEVER_MATCHES``
# individually shipped 161 passed in all three cases.
_MECHANISM_DENIALS = [
    (
        re.compile(r"no\s+mechanism", re.I),
        "The engine has no mechanism for per-sector stress.",
    ),
    (
        re.compile(r"mechanism\s+for\s+stressing", re.I),
        "There is no mechanism for stressing a single segment.",
    ),
    (
        re.compile(r"lacks?\s+(?:the\s+|any\s+|a\s+)?mechanism", re.I),
        "The library lacks the mechanism for per-segment stress.",
    ),
    (
        re.compile(r"without\s+(?:any\s+|the\s+|a\s+)?mechanism", re.I),
        "Shocks are applied without any mechanism for segmentation.",
    ),
    (
        re.compile(
            r"\bno\s+(?:\w+\s+){0,2}"
            r"(?:mechanism|capability|capacity|way|means|ability|support|facility|provision)"
            r"\s+(?:for|to)\s+(?:\w+\s+){0,3}"
            r"(?:stress|target|shock|segment|differentiat)",
            re.I,
        ),
        "The engine has no capability for stressing one sector or geography.",
    ),
    (
        re.compile(
            r"\b(?:cannot|can\s+not|can't|is\s+unable\s+to|are\s+unable\s+to"
            r"|unable\s+to|no\s+way\s+to|not\s+possible\s+to|impossible\s+to)"
            r"\s+(?:\w+\s+){0,3}"
            r"(?:stress|target|shock|differentiate|distinguish)\w*"
            r"\s+(?:\w+\s+){0,3}(?:sector|segment|geograph)",
            re.I,
        ),
        "The engine cannot stress one sector or geography and not another.",
    ),
    (
        re.compile(
            r"\b(?:does|do|did)\s+not\s+(?:\w+\s+){0,2}"
            r"(?:resolve|carry)\w*\s+(?:\w+\s+){0,3}(?:sector|per[- ]loan)",
            re.I,
        ),
        "The engine does not resolve sector per loan.",
    ),
]

# Wordings that must NOT trip the sweep.  Without these, the natural response to
# a false positive is to weaken a pattern back toward inertness; these pin the
# true statements the documents actually make.
_MECHANISM_NON_DENIALS = [
    "Scenario shocks are portfolio-wide - there is no sector or geographic targeting.",
    "A scenario's noi_shock and default_rate_multiplier are scalars with no "
    "per-segment override, and run_simulation applies them to every loan.",
    "What is missing is calibration, not mechanism. The engine already resolves "
    "each loan's sector into a per-loan baseline default rate.",
    "What does not exist is a primary source for how much harder a retail book "
    "should be shocked than a multifamily one.",
]

# The exact sentence that shipped in the notebook and survived the 0.2.0 wording
# fix.  Kept verbatim so the patterns above can be proven non-inert.
#
# NOTE TO A FUTURE AUDITOR: this is the ONLY remaining occurrence of that wording
# anywhere in the repo or the sdist, and it is deliberate.  `grep -rn "mechanism
# for stressing one sector"` returning exactly this line is the expected state;
# a second hit anywhere else is the defect.  tests/ is excluded from the sweep in
# `_prose_artifacts` precisely so this file can quote what it forbids.
# The heading that identifies the notebook's scenario section. Anchored on the
# words, not the section number, so renumbering the notebook does not silently
# unscope the gate -- the "exactly one cell" assertion catches that instead.
_SCENARIO_HEADING = "Custom Labelled Scenarios"

_THE_SENTENCE_THAT_SHIPPED = (
    "The engine has no mechanism for stressing one sector or geography and not "
    "another, so a label like \"Retail Crash\" would be misleading."
)


def _denials_in(text: str):
    """``[(pattern, excerpt)]`` for every denial shape ``text`` contains.

    The single place the pattern list is consulted, so the end-to-end probe test
    and the artifact sweep cannot diverge.
    """
    flat = _flat(text)
    hits = []
    for pattern, _probe in _MECHANISM_DENIALS:
        match = pattern.search(flat)
        if match:
            hits.append(
                (pattern.pattern, flat[max(0, match.start() - 60) : match.end() + 60])
            )
    return hits


def _prose_artifacts():
    """``(label, text)`` for every tracked artifact a reader can act on.

    Covers README, CHANGELOG, every shipped/generator ``.py``, and -- the gap
    this exists to close -- every MARKDOWN cell of the demo notebook.
    ``scripts/render_notebook.py`` executes code cells only, so notebook prose
    was gated by nothing at all; that is how the false sector claim survived
    the 0.2.0 rewrite of ``builder.py``, README limitation 1 and the CHANGELOG.

    ``tests/`` is deliberately excluded: this gate and the docstring gate above
    have to quote the forbidden wording in order to forbid it.
    """
    import json

    from render_notebook import NOTEBOOK

    items = [
        (name, (REPO_ROOT / name).read_text(encoding="utf-8"))
        for name in ("README.md", "CHANGELOG.md")
    ]
    for package in ("cdfistress", "scripts"):
        for path in sorted((REPO_ROOT / package).rglob("*.py")):
            items.append(
                (str(path.relative_to(REPO_ROOT)), path.read_text(encoding="utf-8"))
            )
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    for index, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") == "markdown":
            items.append(
                (f"{NOTEBOOK.name} markdown cell [{index}]", "".join(cell["source"]))
            )
    return items


class TestNoTrackedArtifactDeniesTheMechanism:
    """The 0.2.0 wording fix reached builder.py, the README and the CHANGELOG.

    It did not reach the notebook, because nothing swept notebook prose. These
    tests sweep every artifact a reader can act on, not just the ones someone
    remembered to fix.
    """

    def test_every_denial_pattern_is_individually_live(self):
        """EACH pattern must match its own probe, one probe per pattern.

        The guard this replaces was ``assert any(...)`` over a single shipped
        sentence. Patterns 3 and 4 never matched that sentence and were never
        exercised at all: replacing pattern 1, 3 or 4 with
        ``ZZZZQQQ_NEVER_MATCHES`` individually shipped 161 passed in all three
        cases -- four patterns, one live tripwire.
        """
        dead = [
            pattern.pattern
            for pattern, probe in _MECHANISM_DENIALS
            if not pattern.search(_flat(probe))
        ]
        assert not dead, (
            f"{len(dead)} denial pattern(s) do not match their own probe and are "
            f"therefore inert: {dead}"
        )

    def test_every_denial_probe_is_caught_by_the_sweep_end_to_end(self):
        """Each probe must be flagged by the sweep helper, not just by its regex.

        Proves the pattern list is actually the list the sweep consults.
        """
        uncaught = [probe for _, probe in _MECHANISM_DENIALS if not _denials_in(probe)]
        assert not uncaught, f"the sweep does not flag its own probes: {uncaught}"

    def test_the_sentence_that_shipped_is_still_caught(self):
        """The specific wording this round exists because of."""
        assert _denials_in(_THE_SENTENCE_THAT_SHIPPED)

    def test_the_paraphrases_that_walked_through_are_caught_now(self):
        """The five live survivors measured against the four-pattern version.

        Every one of these, inserted into the notebook's scenario cell, shipped
        161 passed before this commit.
        """
        survivors = [
            "The engine cannot stress one sector or geography and not another.",
            "There is no way to stress one sector or geography and not another.",
            "The engine is unable to target a single sector or geography.",
            "The engine has no capability for stressing one sector or geography.",
            "The engine does not resolve sector per loan.",
        ]
        missed = [s for s in survivors if not _denials_in(s)]
        assert not missed, f"denial paraphrases still walk through the sweep: {missed}"

    def test_the_sweep_does_not_flag_the_true_statements(self):
        """Over-broad patterns would be 'fixed' by weakening them back to inert."""
        offenders = {s: _denials_in(s) for s in _MECHANISM_NON_DENIALS if _denials_in(s)}
        assert not offenders, (
            "the denial sweep flags statements that are TRUE and that the "
            f"documents deliberately make: {offenders}"
        )

    def test_the_sweep_covers_the_notebook_markdown_and_the_docs(self):
        """Guard against the sweep silently iterating over nothing."""
        labels = [label for label, _ in _prose_artifacts()]
        assert "README.md" in labels
        assert "CHANGELOG.md" in labels
        assert any(label.endswith("scenarios/builder.py") for label in labels)
        markdown_cells = [label for label in labels if "markdown cell" in label]
        assert len(markdown_cells) >= 5, (
            f"only {len(markdown_cells)} notebook markdown cells swept; the "
            "notebook prose gap is not actually covered"
        )

    def test_no_tracked_artifact_claims_the_engine_lacks_the_mechanism(self):
        offenders = []
        for label, text in _prose_artifacts():
            for pattern_source, excerpt in _denials_in(text):
                offenders.append(f"{label}: [{pattern_source}] ...{excerpt}...")
        assert not offenders, (
            "artifact(s) claim the engine has no per-segment mechanism. It has one: "
            "_compute_loss_distribution and default_probabilities both resolve "
            "SECTOR_DEFAULT_RATES per loan. What is missing is calibration. "
            + "\n".join(offenders)
        )

    def test_the_notebook_scenario_section_was_actually_isolated(self):
        """Guard: if the heading is renamed, the gate below covers nothing."""
        index, source = _markdown_cell_containing(_SCENARIO_HEADING)
        joined = "".join(src for _, src in _markdown_cells())
        assert source.strip(), f"markdown cell [{index}] is empty"
        assert len(source) < len(joined), "scenario-cell scoping did not narrow anything"

    def test_the_notebook_scenario_section_states_calibration_not_mechanism(self):
        """The positive half, SCOPED TO THE CELL THAT MAKES THE CLAIM.

        Deleting the paragraph outright would satisfy the negative sweep above,
        so a positive gate is required -- but the version this replaces joined
        every markdown cell and searched the union, which is the same defect
        class the API-surface gate was anchored to eliminate in this very commit.
        Proven: rewriting this cell's key line to "Sector targeting is simply
        unsupported today.", dropping its SECTOR_DEFAULT_RATES mention, and
        parking "Unrelated aside: calibration, not mechanism.
        SECTOR_DEFAULT_RATES." in cell [0] shipped 161 passed.
        """
        index, source = _markdown_cell_containing(_SCENARIO_HEADING)
        flat = _flat(source)
        assert "calibration, not mechanism" in flat.lower(), (
            f"notebook markdown cell [{index}] -- the scenario section -- no longer "
            "states that what is missing is calibration, not mechanism, which is "
            "the wording builder.py and README limitation 1 use.\n"
            f"--- cell ---\n{source}"
        )
        assert "SECTOR_DEFAULT_RATES" in flat, (
            f"notebook markdown cell [{index}] no longer names the per-loan "
            "mechanism it rests the claim on"
        )
        assert not _denials_in(source), (
            f"the scenario cell itself denies the mechanism: {_denials_in(source)}"
        )


class TestSectorDifferentiationClaim:
    """The claim the 0.2.0 wording change rests on is itself a measured figure."""

    def test_the_quoted_sector_and_pd_counts_are_real(self, documented_portfolio):
        from cdfistress.data.schema import SECTOR_DEFAULT_RATES

        words = {"three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
        # EVERY occurrence, not the first: the changelog quotes this sentence again
        # when recording that its portfolio size was ungated, and a gate anchored
        # on `re.search` would leave that copy free to drift.
        matches = list(
            re.finditer(r"spans (\w+) sectors and (\w+)\s*\n?\s*distinct PDs", CHANGELOG)
        )
        assert matches, "CHANGELOG no longer states the sector/PD counts"
        assert len({(m.group(1), m.group(2)) for m in matches}) == 1, (
            f"the changelog's copies of the sector/PD counts disagree: "
            f"{[(m.group(1), m.group(2)) for m in matches]}"
        )
        match = matches[0]

        # The SAME SENTENCE states the portfolio size, and that half was ungated:
        # `"50-loan"` -> `"900-loan"` shipped 161 passed. Gating one half of a
        # sentence and leaving the other is how this defect keeps recurring.
        sizes = [
            int(m.group(1))
            for m in re.finditer(r"the (\d+)-loan sample portfolio spans", CHANGELOG)
        ]
        assert sizes, "CHANGELOG no longer states the sample portfolio size"
        wrong = [n for n in sizes if n != len(documented_portfolio)]
        assert not wrong, (
            f"CHANGELOG states {wrong}-loan sample portfolio(s); the documented "
            f"portfolio has {len(documented_portfolio)} loans"
        )
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

    def test_the_notebooks_copy_of_the_same_counts_is_real(self, documented_portfolio):
        """The notebook prose repeats these counts, so it is a measured figure too.

        The CHANGELOG's copy was gated; the notebook's was not, because nothing
        swept notebook markdown at all. Adding the sentence without this gate
        would have reintroduced exactly the defect this round exists to close:
        a hand-typed number in an artifact nothing re-derives.
        """
        import json

        from render_notebook import NOTEBOOK

        words = {"three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
        notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        markdown = " ".join(
            " ".join("".join(c["source"]).split())
            for c in notebook["cells"]
            if c.get("cell_type") == "markdown"
        )
        match = re.search(r"produces (\w+) distinct PDs across (\w+) sectors", markdown)
        assert match, "the notebook no longer states the distinct-PD / sector counts"
        stated_pds = words[match.group(1).lower()]
        stated_sectors = words[match.group(2).lower()]

        # The notebook builds its portfolio with the same call the quickstart does.
        engine = MonteCarloEngine(loans=documented_portfolio, available_capital=5_000_000)
        actual_pds = len(set(engine.default_probabilities(from_standard("2008_recession")).values()))
        actual_sectors = len({loan.sector for loan in documented_portfolio})

        assert (stated_pds, stated_sectors) == (actual_pds, actual_sectors), (
            f"notebook says {stated_pds} distinct PDs across {stated_sectors} sectors; "
            f"measured {actual_pds} across {actual_sectors}"
        )

    def test_the_notebook_and_changelog_state_the_same_counts(self):
        """Two documents, one measurement. 0.1.0's defect was letting them diverge."""
        import json

        from render_notebook import NOTEBOOK

        notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        markdown = " ".join(
            " ".join("".join(c["source"]).split())
            for c in notebook["cells"]
            if c.get("cell_type") == "markdown"
        )
        nb_match = re.search(r"produces (\w+) distinct PDs across (\w+) sectors", markdown)
        cl_match = re.search(r"spans (\w+) sectors and (\w+)\s*\n?\s*distinct PDs", CHANGELOG)
        assert nb_match and cl_match
        assert nb_match.group(1).lower() == cl_match.group(2).lower(), "PD counts disagree"
        assert nb_match.group(2).lower() == cl_match.group(1).lower(), "sector counts disagree"


# --------------------------------------------------------------------------
# Notebook markdown figure inventory.
#
# Fourteen figures in this notebook's prose were proven ungated by mutation --
# every one shipped 161 passed -- including BOTH test-file paths named in the
# very paragraph that told readers the prose was gated. Two of the fourteen were
# self-referential, which is the shape the CHANGELOG already records finding
# once: ``render_readme_block.py`` claimed its gate lived in
# ``tests/test_readme_artifact.py``, a file that has never existed.
#
# Each entry below is (label, pattern). ``_FIGURE_GATES`` maps every label to the
# test that DERIVES that figure, and ``test_every_inventory_label_has_a_value_gate``
# fails if a pattern is added without one -- otherwise the inventory sweep could
# be silenced by adding a catch-all pattern that consumes tokens and checks
# nothing.
# --------------------------------------------------------------------------

_FIGURE_PATTERNS = [
    # URLs first: they carry digits (the GitHub owner name) that are not figures,
    # and consuming them whole keeps the narrower patterns from nibbling at them.
    ("project URL", re.compile(r"https?://[^\s)>\]]+")),
    ("portfolio size", re.compile(r"\b(\d+)-loan\b")),
    ("portfolio size", re.compile(r"\b(\d+) loans across sectors\b")),
    ("iteration count", re.compile(r"\b([\d,]+)\s+(?:Monte Carlo\s+)?iterations\b")),
    ("VaR confidence levels", re.compile(r"\b(\d+)% and (\d+)% confidence levels\b")),
    ("release version", re.compile(r"\b(\d+\.\d+\.\d+)\b")),
    ("README limitation index", re.compile(r"Known limitations\W{0,3}\s*item (\d+)")),
    ("test file path", re.compile(r"`(tests/[A-Za-z0-9_./-]+\.py)`")),
    ("scenario year", re.compile(r"\b((?:19|20)\d{2})\b")),
    ("basis points", re.compile(r"\+?(\d+)\s*bps\b")),
]

_FIGURE_GATES = {
    "project URL": "test_every_url_named_matches_the_declared_project_metadata",
    "portfolio size": "test_the_stated_portfolio_size_is_the_one_the_notebook_generates",
    "iteration count": "test_every_stated_iteration_count_is_one_a_code_cell_runs",
    "VaR confidence levels": "test_the_stated_confidence_levels_are_the_ones_computed",
    "release version": "test_every_version_named_is_a_release_the_changelog_records",
    "README limitation index": "test_the_cited_readme_limitation_is_the_portfolio_wide_one",
    "test file path": "test_every_test_file_named_exists_and_does_the_job_claimed",
    "scenario year": "test_every_year_named_comes_from_a_standard_scenario",
    "basis points": "test_every_bps_figure_named_comes_from_a_standard_scenario",
}

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
}


def _notebook_generated_portfolio():
    """The portfolio the notebook's OWN code cell builds -- not the quickstart's."""
    for source in _code_cells():
        match = re.search(r"generate_sample_portfolio\(n=(\d+),\s*seed=(\d+)\)", source)
        if match:
            return generate_sample_portfolio(
                n=int(match.group(1)), seed=int(match.group(2))
            )
    raise AssertionError("no notebook code cell generates a sample portfolio")


def _changelog_releases():
    """``{version: body}`` for every ``## [x.y.z]`` section of the CHANGELOG."""
    parts = re.split(r"^## \[(\d+\.\d+\.\d+)\][^\n]*$", CHANGELOG, flags=re.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


class TestNotebookMarkdownFigures:
    """Every figure the notebook's prose states is re-derived, never trusted."""

    def test_the_markdown_sweep_covers_the_cells_it_claims_to(self):
        """Guard: every gate here iterates over this list."""
        cells = _markdown_cells()
        assert len(cells) >= 10, f"only {len(cells)} markdown cells found"
        assert any("Summary" in src for _, src in cells)

    # -- portfolio size -----------------------------------------------------

    def test_the_stated_portfolio_size_is_the_one_the_notebook_generates(self):
        """`"50-loan"` -> `"900-loan"` shipped 161 passed, in three places."""
        actual = len(_notebook_generated_portfolio())
        stated = [
            int(match.group(1))
            for _, source in _markdown_cells()
            for pattern in (
                re.compile(r"\b(\d+)-loan\b"),
                re.compile(r"\b(\d+) loans across sectors\b"),
            )
            for match in pattern.finditer(_flat(source))
        ]
        assert len(stated) >= 3, (
            f"expected the notebook prose to state the portfolio size at least "
            f"three times; found {stated}"
        )
        wrong = [n for n in stated if n != actual]
        assert not wrong, f"prose states portfolio size(s) {wrong}; the notebook builds {actual}"

    # -- iteration count ----------------------------------------------------

    def test_every_stated_iteration_count_is_one_a_code_cell_runs(self):
        used = {
            int(match.group(1))
            for source in _code_cells()
            for match in re.finditer(r"n_iterations=(\d+)", source)
        }
        assert used, "no notebook code cell passes n_iterations; the gate covers nothing"
        stated = [
            int(match.group(1).replace(",", ""))
            for _, source in _markdown_cells()
            for match in re.finditer(
                r"\b([\d,]+)\s+(?:Monte Carlo\s+)?iterations\b", _flat(source)
            )
        ]
        assert stated, "the notebook prose states no iteration count"
        wrong = [n for n in stated if n not in used]
        assert not wrong, f"prose states iteration counts {wrong}; code cells run {sorted(used)}"

    def test_a_sections_iteration_count_matches_the_cell_it_introduces(self):
        """Not just 'some cell somewhere' -- the cell that section runs."""
        cells = _notebook()["cells"]
        checked = 0
        for index, cell in enumerate(cells):
            if cell.get("cell_type") != "markdown":
                continue
            match = re.search(
                r"\b([\d,]+)\s+Monte Carlo\s+iterations\b", _flat("".join(cell["source"]))
            )
            if not match:
                continue
            following = next(
                (c for c in cells[index + 1 :] if c.get("cell_type") == "code"), None
            )
            assert following is not None, f"markdown cell [{index}] introduces no code cell"
            used = [
                int(m.group(1))
                for m in re.finditer(r"n_iterations=(\d+)", "".join(following["source"]))
            ]
            stated = int(match.group(1).replace(",", ""))
            assert stated in used, (
                f"markdown cell [{index}] announces {stated:,} iterations but the code "
                f"cell it introduces runs {used}"
            )
            checked += 1
        assert checked, "no notebook section announces a Monte Carlo iteration count"

    # -- confidence levels --------------------------------------------------

    def test_the_stated_confidence_levels_are_the_ones_computed(self):
        used = {
            round(float(match.group(1)) * 100)
            for source in _code_cells()
            for match in re.finditer(r"confidence=(0\.\d+)", source)
        }
        assert used, "no notebook code cell passes a confidence level"
        pairs = [
            (int(m.group(1)), int(m.group(2)))
            for _, source in _markdown_cells()
            for m in re.finditer(r"\b(\d+)% and (\d+)% confidence levels\b", _flat(source))
        ]
        assert pairs, "the notebook prose states no VaR confidence levels"
        for low, high in pairs:
            assert {low, high} <= used, (
                f"prose promises VaR at {low}% and {high}%; the notebook computes "
                f"{sorted(used)}"
            )

    # -- versions -----------------------------------------------------------

    def test_every_version_named_is_a_release_the_changelog_records(self):
        known = set(_changelog_releases()) | {cdfistress.__version__}
        assert len(known) >= 2, f"only {known} parsed from the CHANGELOG"
        named = {
            match.group(1)
            for _, source in _markdown_cells()
            for match in re.finditer(r"\b(\d+\.\d+\.\d+)\b", source)
        }
        assert named, "the notebook prose names no version"
        unknown = sorted(named - known)
        assert not unknown, f"notebook prose names releases that do not exist: {unknown}"

    def test_the_notebook_names_the_release_that_removed_the_sector_constructor(self):
        """Both 0.1.0 and 0.2.0 in the scenario cell were hand-typed and ungated."""
        owning = [
            version
            for version, body in _changelog_releases().items()
            if "### Removed - `create_sector_specific_scenario`" in body
        ]
        assert len(owning) == 1, f"CHANGELOG records the removal in {owning}"
        _index, source = _markdown_cell_containing(_SCENARIO_HEADING)
        flat = _flat(source)

        removed_in = re.search(r"was removed in (\d+\.\d+\.\d+)", flat)
        assert removed_in, f"the scenario cell no longer says which release removed it:\n{source}"
        assert removed_in.group(1) == owning[0], (
            f"notebook says the constructor was removed in {removed_in.group(1)}; "
            f"the CHANGELOG records the removal under {owning[0]}"
        )

        shipped_in = re.search(
            r"(\d+\.\d+\.\d+)'s `create_sector_specific_scenario`", flat
        )
        assert shipped_in, f"the scenario cell no longer says which release shipped it:\n{source}"
        assert shipped_in.group(1) in _changelog_releases()
        assert shipped_in.group(1) != owning[0], (
            "the notebook says the same release both shipped and removed the constructor"
        )

    def test_the_summary_names_the_same_release_for_the_wording_fix(self):
        """Cell 22's 'the 0.2.0 sector-scenario wording' was ungated."""
        owning = [
            version
            for version, body in _changelog_releases().items()
            if "### Removed - `create_sector_specific_scenario`" in body
        ]
        markdown = " ".join(_flat(source) for _, source in _markdown_cells())
        match = re.search(r"the (\d+\.\d+\.\d+) sector-scenario wording", markdown)
        assert match, "the notebook summary no longer dates the sector-scenario wording"
        assert match.group(1) == owning[0]

    # -- named artifacts ----------------------------------------------------

    def test_every_test_file_named_exists_and_does_the_job_claimed(self):
        """Both paths named in cell 22 were ungated -- in the paragraph that
        told readers this notebook's prose was gated.

        Existence alone is not enough: the CHANGELOG already records a claim that
        named a plausible-but-nonexistent gate file, so each named file must also
        actually reference the notebook it is credited with covering.
        """
        named = {
            match.group(1)
            for _, source in _markdown_cells()
            for match in re.finditer(r"`(tests/[A-Za-z0-9_./-]+\.py)`", source)
        }
        assert len(named) >= 2, f"the notebook prose names {named}; expected at least two"
        missing = sorted(name for name in named if not (REPO_ROOT / name).is_file())
        assert not missing, f"the notebook names test files that do not exist: {missing}"
        inert = sorted(
            name
            for name in named
            if "notebook" not in (REPO_ROOT / name).read_text(encoding="utf-8").lower()
        )
        assert not inert, (
            f"the notebook credits {inert} with covering it, but those files never "
            "mention the notebook"
        )
        # The prose also states HOW MANY it names, in word form. The inventory
        # gate below scans digits only, so a word-form count needs its own gate.
        markdown = " ".join(_flat(source) for _, source in _markdown_cells())
        stated = re.search(r"the (\w+) test files it names", markdown)
        assert stated, "the notebook no longer states how many test files it names"
        assert _WORD_NUMBERS[stated.group(1).lower()] == len(named), (
            f"the notebook says it names {stated.group(1)} test files; it names "
            f"{len(named)}: {sorted(named)}"
        )

    def test_every_url_named_matches_the_declared_project_metadata(self):
        """The GitHub and PyPI links in the summary were hand-typed too.

        A link to the wrong repository is the same failure as a path to a test
        file that does not exist, with a worse blast radius.
        """
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        declared = {
            url.rstrip("/")
            for url in re.findall(r'^\s*\w+\s*=\s*"(https?://[^"]+)"', pyproject, re.M)
        }
        assert declared, "pyproject.toml declares no project URL"
        name = re.search(r'^name\s*=\s*"([^"]+)"', pyproject, re.M).group(1)
        allowed = declared | {f"https://pypi.org/project/{name}"}

        named = {
            match.group(0).rstrip("/.,")
            for _, source in _markdown_cells()
            for match in re.finditer(r"https?://[^\s)>\]]+", source)
        }
        assert named, "the notebook prose names no URL"
        stray = sorted(url for url in named if url.rstrip("/") not in allowed)
        assert not stray, (
            f"the notebook links to {stray}, which the project metadata does not "
            f"declare (declared: {sorted(allowed)})"
        )

    def test_the_cited_readme_limitation_is_the_portfolio_wide_one(self):
        """`See "Known limitations" item 1` -- the number was hand-typed."""
        _index, source = _markdown_cell_containing(_SCENARIO_HEADING)
        match = re.search(r"Known limitations\W{0,3}\s*item (\d+)", _flat(source))
        assert match, f"the scenario cell no longer cites a README limitation:\n{source}"
        stated = int(match.group(1))

        section = README.split("## Known limitations", 1)[1].split("\n## ", 1)[0]
        items = re.findall(r"^(\d+)\. \*\*(.+)$", section, re.M)
        assert items, "could not parse the README's numbered limitations"
        matching = [
            int(number)
            for number, title in items
            if "portfolio-wide" in title.lower() and "targeting" in title.lower()
        ]
        assert matching == [stated], (
            f"the notebook cites Known limitations item {stated}; the "
            f"portfolio-wide-shocks limitation is item {matching} "
            f"(README items: {[(n, ti[:50]) for n, ti in items]})"
        )

    # -- scenarios and sectors ---------------------------------------------

    def test_every_year_named_comes_from_a_standard_scenario(self):
        names = " ".join(from_standard(key).name for key in STANDARD_SCENARIOS)
        years = {
            match.group(1)
            for _, source in _markdown_cells()
            for match in re.finditer(r"\b((?:19|20)\d{2})\b", source)
        }
        assert years, "the notebook prose names no scenario year"
        stray = sorted(year for year in years if year not in names)
        assert not stray, f"prose names year(s) {stray} that no standard scenario carries"

    def test_every_bps_figure_named_comes_from_a_standard_scenario(self):
        rendered = {
            round(from_standard(key).rate_shock * 10_000) for key in STANDARD_SCENARIOS
        }
        stated = {
            int(match.group(1))
            for _, source in _markdown_cells()
            for match in re.finditer(r"\+?(\d+)\s*bps\b", source)
        }
        wrong = sorted(value for value in stated if value not in rendered)
        assert not wrong, f"prose states {wrong} bps; scenarios render {sorted(rendered)}"

    def test_the_summary_scenario_list_covers_every_standard_scenario(self):
        """The list omitted `mild_downturn` entirely, and nothing noticed."""
        _index, source = _markdown_cell_containing("Standard stress scenarios")
        match = re.search(r"\*\*Standard stress scenarios\*\*[^A-Za-z0-9]+([^\n]+)", source)
        assert match, f"could not find the summary scenario list:\n{source}"
        listed = [item.strip() for item in match.group(1).split(",") if item.strip()]
        assert len(listed) == len(STANDARD_SCENARIOS), (
            f"the summary lists {len(listed)} scenarios ({listed}); the library "
            f"ships {len(STANDARD_SCENARIOS)}: {sorted(STANDARD_SCENARIOS)}"
        )
        words = {
            key: set(re.findall(r"[a-z0-9]+", from_standard(key).name.lower()))
            for key in STANDARD_SCENARIOS
        }
        haystack = match.group(1).lower()
        for key, own in words.items():
            others = set().union(*(v for other, v in words.items() if other != key))
            distinctive = own - others
            assert distinctive, f"{key} has no word that distinguishes it"
            assert any(word in haystack for word in distinctive), (
                f"the summary scenario list never names {key} "
                f"({from_standard(key).name}); expected one of {sorted(distinctive)}"
            )

    def test_the_sector_sentence_matches_the_portfolio_and_the_rate_table(self):
        """Cell 2 said the portfolio spans "the sectors the library tracks" and
        listed six. ``SECTOR_DEFAULT_RATES`` has seven; ``other`` was omitted.
        """
        from cdfistress.data.schema import SECTOR_DEFAULT_RATES

        _index, source = _markdown_cell_containing("Generate a Sample CDFI Portfolio")
        flat = _flat(source)
        match = re.search(
            r"spanning (\w+) of the (\w+) sectors the library tracks: ([^.]+)\.", flat
        )
        assert match, f"could not parse the sector sentence:\n{source}"
        stated_drawn = _WORD_NUMBERS[match.group(1).lower()]
        stated_tracked = _WORD_NUMBERS[match.group(2).lower()]

        listed = set()
        for item in match.group(3).split(","):
            name = item.strip().removeprefix("and ").strip().replace(" ", "_")
            if name:
                listed.add(name)

        drawn = {loan.sector for loan in _notebook_generated_portfolio()}
        assert stated_tracked == len(SECTOR_DEFAULT_RATES), (
            f"prose says the library tracks {stated_tracked} sectors; "
            f"SECTOR_DEFAULT_RATES has {len(SECTOR_DEFAULT_RATES)}"
        )
        assert stated_drawn == len(drawn), (
            f"prose says the portfolio spans {stated_drawn} sectors; it spans {len(drawn)}"
        )
        assert listed == drawn, (
            f"prose lists {sorted(listed)}; the portfolio contains {sorted(drawn)}"
        )
        untouched = set(SECTOR_DEFAULT_RATES) - drawn
        assert untouched, (
            "the sample portfolio now draws every tracked sector; the sentence's "
            "'six of the seven' framing is stale"
        )
        for name in sorted(untouched):
            assert f"`{name}`" in flat, (
                f"prose does not name the tracked-but-undrawn sector {name!r}"
            )

    # -- the inventory itself ----------------------------------------------

    def test_every_inventory_label_has_a_value_gate(self):
        """A pattern without a gate would consume tokens and check nothing."""
        labels = {label for label, _ in _FIGURE_PATTERNS}
        assert labels == set(_FIGURE_GATES), (
            f"inventory labels {sorted(labels)} do not match the gate registry "
            f"{sorted(_FIGURE_GATES)}"
        )
        missing = [
            name for name in _FIGURE_GATES.values() if not hasattr(type(self), name)
        ]
        assert not missing, f"_FIGURE_GATES names tests that do not exist: {missing}"

    def test_every_inventory_pattern_matches_something(self):
        """A pattern that matches nothing is a gate covering nothing."""
        joined = "\n".join(source for _, source in _markdown_cells())
        dead = sorted(
            {label for label, pattern in _FIGURE_PATTERNS if not pattern.search(joined)}
        )
        # bps is the one figure the notebook prose may legitimately not state.
        assert dead in ([], ["basis points"]), f"inventory patterns match nothing: {dead}"

    def test_no_ungated_figure_shaped_token_remains_in_notebook_markdown(self):
        """THE gate that makes the summary's claim about itself true.

        Every figure the prose states must be consumed by a pattern that a value
        gate above re-derives. A new hand-typed number added to this markdown
        fails here until it is gated. Structural numbering -- heading numbers and
        ordered-list markers -- is stripped first; it is navigation, not a claim.

        SCOPE, precisely: this scans for DIGITS. A count spelled as a word
        ("six sectors", "two test files") is invisible to it, so each word-form
        count in the prose carries its own named gate above --
        ``test_the_notebooks_copy_of_the_same_counts_is_real``,
        ``test_the_sector_sentence_matches_the_portfolio_and_the_rate_table`` and
        ``test_every_test_file_named_exists_and_does_the_job_claimed``. A NEW
        word-form count added to this markdown would not be caught here.
        """
        residue = {}
        for index, source in _markdown_cells():
            text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+\d+\.\s", "", source)
            text = re.sub(r"(?m)^\s{0,3}\d+\.\s", "", text)
            for _label, pattern in _FIGURE_PATTERNS:
                text = pattern.sub(" ", text)
            left = re.findall(r"\d[\d,.]*", text)
            if left:
                residue[index] = left
        assert not residue, (
            "notebook markdown states figures that no gate re-derives: "
            f"{residue}\nAdd a value gate and an entry to _FIGURE_PATTERNS / "
            "_FIGURE_GATES, or remove the figure from the prose."
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
