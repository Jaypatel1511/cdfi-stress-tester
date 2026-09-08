"""Gates on the public API surface, the docs that describe it, and version sites.

These exist because 0.1.0 documented functions whose behaviour did not match their
name (``create_sector_specific_scenario`` ignored ``sector``), a method with a
parameter it never read (``simulate_default_events(seed=...)``), and a report that
labelled a 300 bps shock as "+3 bps".
"""
import ast
import inspect
import re
import textwrap

import numpy
from pathlib import Path

import pytest

import cdfistress
from cdfistress import (
    MonteCarloEngine,
    create_recession_scenario,
    from_standard,
    generate_sample_portfolio,
    generate_stress_report,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

# Public names that carry a `.member` in the README API reference.
_DOC_CLASSES = [
    cdfistress.MonteCarloEngine,
    cdfistress.Loan,
    cdfistress.StressScenario,
    cdfistress.StressResult,
]


class TestVersionSites:
    """Every place the version is written must agree. Counts are derived."""

    def _sites(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        setup_py = (REPO_ROOT / "setup.py").read_text(encoding="utf-8")
        sites = {
            "cdfistress.__version__": cdfistress.__version__,
            "pyproject.toml": re.search(
                r'^version\s*=\s*"([^"]+)"', pyproject, re.M
            ).group(1),
            "setup.py": re.search(r'version\s*=\s*"([^"]+)"', setup_py).group(1),
        }
        return sites

    def test_all_version_sites_agree(self):
        sites = self._sites()
        distinct = set(sites.values())
        assert len(distinct) == 1, f"version sites disagree: {sites}"

    def test_version_is_pep440_and_not_the_defective_release(self):
        version = cdfistress.__version__
        assert re.fullmatch(r"\d+\.\d+\.\d+", version), version
        # 0.1.0's README was wrong in every figure; it must never be re-published.
        assert version != "0.1.0"

    def test_no_unscanned_version_string_left_behind(self):
        """No tracked source file may still carry the previous version literal."""
        previous = "0.1.0"
        offenders = []
        for path in [
            REPO_ROOT / "pyproject.toml",
            REPO_ROOT / "setup.py",
            REPO_ROOT / "cdfistress" / "__init__.py",
        ]:
            # Matches both `version = "x"` and `__version__ = "x"`. A naive
            # `version\s*=` pattern silently misses the dunder form, because the
            # word "version" there is followed by "__" rather than "=".
            pattern = rf'(?:__)?version(?:__)?\s*=\s*"{re.escape(previous)}"'
            if re.search(pattern, path.read_text(encoding="utf-8")):
                offenders.append(path.name)
        assert not offenders, f"stale version literal in: {offenders}"


class TestSectorScenarioRemoved:
    """0.1.0's create_sector_specific_scenario ignored its `sector` argument."""

    def test_not_exported(self):
        assert not hasattr(cdfistress, "create_sector_specific_scenario")
        assert "create_sector_specific_scenario" not in cdfistress.__all__

    def test_not_importable_from_builder(self):
        from cdfistress.scenarios import builder

        assert not hasattr(builder, "create_sector_specific_scenario")

    def test_no_scenario_constructor_takes_a_sector_argument(self):
        """Nothing may reintroduce a `sector` parameter that does not isolate a sector."""
        from cdfistress.scenarios import builder

        offenders = []
        for name, obj in vars(builder).items():
            if not (inspect.isfunction(obj) and name.startswith("create_")):
                continue
            if "sector" in inspect.signature(obj).parameters:
                offenders.append(name)
        assert not offenders, (
            f"{offenders} accept a `sector` parameter, but the engine applies shocks "
            "portfolio-wide and cannot isolate a sector. See README 'Known limitations'."
        )

    def test_labels_do_not_change_the_simulation(self):
        """`name` is a label only. A scenario cannot be targeted by naming it.

        Compared field by field rather than on a summary statistic, so any leak of
        `name` into a shock value is caught regardless of whether two particular
        names happen to collide under whatever function leaked them.
        """
        shocks = dict(
            noi_shock=-0.30,
            rate_shock=0.01,
            property_value_shock=-0.35,
            default_rate_multiplier=2.5,
        )
        # Names chosen to differ in first character, length, character sum and
        # content, so a leak cannot survive by colliding under any one of them.
        a = create_recession_scenario(name="A", severity="moderate", **shocks)
        b = create_recession_scenario(name="bcdefghijklm", severity="moderate", **shocks)
        assert a.name != b.name
        assert a.name[0] != b.name[0]
        assert len(a.name) != len(b.name)
        assert sum(map(ord, a.name)) != sum(map(ord, b.name))
        assert ord(a.name[0]) % 5 != ord(b.name[0]) % 5

        leaked = [
            field
            for field in a.__dataclass_fields__
            if field != "name" and getattr(a, field) != getattr(b, field)
        ]
        assert not leaked, f"scenario `name` leaked into shock field(s): {leaked}"

        # ...and the two produce identical losses path for path.
        loans = generate_sample_portfolio(n=30, seed=3)
        engine = MonteCarloEngine(loans=loans, available_capital=4_000_000)
        engine.run_simulation(a, n_iterations=200, seed=11)
        losses_a = engine.loss_distribution
        engine.run_simulation(b, n_iterations=200, seed=11)
        losses_b = engine.loss_distribution
        assert numpy.array_equal(losses_a, losses_b)


class TestDefaultProbabilities:
    """0.1.0's simulate_default_events took a `seed` it never used."""

    def test_old_name_is_gone(self):
        assert not hasattr(MonteCarloEngine, "simulate_default_events")

    def test_new_name_exists_and_takes_no_seed(self):
        sig = inspect.signature(MonteCarloEngine.default_probabilities)
        assert "seed" not in sig.parameters, (
            "default_probabilities is deterministic; a `seed` parameter would be "
            "dead weight, which is exactly the 0.1.0 defect."
        )

    def test_no_public_engine_method_accepts_an_unused_seed(self):
        """Any public method advertising `seed` must actually read it.

        Parsed from the AST with the docstring removed: a substring search is not
        enough, because the docstring of a method that ignores `seed` typically
        mentions the word `seed` and would satisfy it.
        """
        offenders = []
        for name in dir(MonteCarloEngine):
            if name.startswith("_"):
                continue
            attr = inspect.getattr_static(MonteCarloEngine, name)
            func = attr.fget if isinstance(attr, property) else attr
            if not inspect.isfunction(func):
                continue
            if "seed" not in inspect.signature(func).parameters:
                continue
            node = ast.parse(textwrap.dedent(inspect.getsource(func))).body[0]
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]  # drop the docstring
            reads_seed = any(
                isinstance(sub, ast.Name) and sub.id == "seed"
                for stmt in body
                for sub in ast.walk(stmt)
            )
            if not reads_seed:
                offenders.append(name)
        assert not offenders, (
            f"public methods declare `seed` but never read it: {offenders}. "
            "That was the 0.1.0 simulate_default_events defect."
        )


class TestBasisPointRendering:
    """A scenario named '+300 bps' reported '+3 bps' in 0.1.0."""

    @pytest.mark.parametrize("key", sorted(cdfistress.STANDARD_SCENARIOS))
    def test_report_and_summary_agree_on_basis_points(self, key):
        scenario = from_standard(key)
        # Derived from the scenario's own value: rate_shock is a decimal fraction,
        # so 0.03 == 300 bps.
        expected = f"{round(scenario.rate_shock * 10_000):+d} bps"

        assert expected in scenario.summary(), (
            f"{key}: summary() rendered {scenario.summary()!r}, expected {expected!r}"
        )

        engine = MonteCarloEngine(
            loans=generate_sample_portfolio(n=5, seed=1), available_capital=1_000_000
        )
        report = generate_stress_report(engine.run_simulation(scenario, 10, seed=0))
        assert expected in report, f"{key}: report missing {expected!r}"

    def test_named_bps_in_scenario_title_matches_rendered_bps(self):
        """Where a scenario's own name states a bps figure, the render must match it."""
        checked = 0
        for key in cdfistress.STANDARD_SCENARIOS:
            scenario = from_standard(key)
            match = re.search(r"([+-]?\d+)\s*bps", scenario.name)
            if not match:
                continue
            checked += 1
            named = int(match.group(1))
            rendered = round(scenario.rate_shock * 10_000)
            assert named == rendered, (
                f"{key}: name says {named} bps but rate_shock renders {rendered} bps"
            )
        assert checked > 0, "no standard scenario states a bps figure in its name"


class TestReadmeDocumentsTheRealApi:
    """The README API reference must match __all__ in both directions."""

    def test_every_exported_name_appears_in_the_readme(self):
        missing = [
            name
            for name in cdfistress.__all__
            if not re.search(rf"\b{re.escape(name)}\b", README)
        ]
        assert not missing, f"exported but undocumented in README: {missing}"

    def test_every_function_call_in_the_api_reference_exists(self):
        block = README.split("## API Reference", 1)[1]
        names = set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\(", block, re.M))
        assert names, "could not parse any names out of the API Reference block"
        unknown = sorted(n for n in names if not hasattr(cdfistress, n))
        assert not unknown, f"README documents names the package does not export: {unknown}"

    def test_every_documented_member_exists_on_some_public_class(self):
        block = README.split("## API Reference", 1)[1]
        members = set(re.findall(r"^\s+\.([a-z_][a-z0-9_]*)", block, re.M))
        assert members, "could not parse any .members out of the API Reference block"
        unknown = sorted(
            m for m in members if not any(hasattr(c, m) for c in _DOC_CLASSES)
        )
        assert not unknown, f"README documents members no public class has: {unknown}"
