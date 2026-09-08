# Changelog

All notable changes to `cdfi-stress-tester` are documented here.

This project follows [Semantic Versioning](https://semver.org/). While the major
version is `0`, breaking changes may land in a minor release.

## [0.2.0] - 2026-09-08

This release corrects documentation that misrepresented the library's output, and
removes two API surfaces that did not do what their names said.

**The simulation math is unchanged.** Every figure below was measured, not estimated.

### Fixed - the 0.1.0 README reported numbers the code never produced

The 0.1.0 README quickstart block was hand-transcribed and wrong in every figure.
Running that README's own snippet verbatim - `generate_sample_portfolio(n=50, seed=42)`,
`MonteCarloEngine(loans=loans, available_capital=5_000_000)`,
`from_standard("2008_recession")`, `run_simulation(n_iterations=1000, seed=42)`:

| Metric | 0.1.0 README claimed | What the code actually printed |
|---|---|---|
| Expected Loss | $2,341,205 | **$8,843,297** |
| VaR (95%) | $3,879,450 | **$15,033,139** |
| VaR (99%) | $4,672,000 | **$17,396,438** |
| CAR vs Expected Loss | 2.14x | **0.57x** |
| Status | ADEQUATE | **INSUFFICIENT** |
| Buffer breaches | not shown | **858 / 1000 (85.8%)** |

The verdict was not merely imprecise, it was **reversed**. A portfolio the README
presented as adequately capitalised in fact breaches its capital buffer on 85.8% of
simulated paths. The stated use cases for this package are CDFI Fund reporting,
rating-agency submissions and board risk committees, so anyone who took the README
at face value was reading a capital position the library never computed. That README
was the package's PyPI landing page from the 0.1.0 upload on 2026-05-11 until this
release.

**The engine was not modified.** 0.1.0 computed $8,843,297 for that scenario and so
does 0.2.0. Only the README was wrong: if you ran the library yourself rather than
reading the README, your numbers were already correct.

The README quickstart is now a generated artifact. `scripts/render_readme_block.py`
owns the snippet, executes it, and writes back exactly what it printed, so the code
shown and the numbers shown provably come from the same run. CI re-renders and
byte-diffs the committed region on every supported interpreter.

### Fixed - the demo notebook had never been executed

`examples/cdfi_stress_test_demo.ipynb` was committed with no outputs and no execution
counts, and 6 of its 11 code cells raised against the library's own API:

| Cell called | Reality |
|---|---|
| `loan.commitment_amount`, `loan.id` | `Loan` has neither field |
| `scenario_comparison_table(...).to_string(index=False)` | returns `str`, not a DataFrame |
| `create_rate_shock_scenario(name=...)` | no `name` parameter |
| `create_sector_specific_scenario(name=..., sector_default_multiplier=...)` | neither parameter existed |
| `capital_adequacy_report(loss_distribution=...)` | parameter is `losses` |
| `tail_loss(..., percentile=99)` | parameter is `pct` (a fraction) |

The notebook's prose also described sectors the sample portfolio does not contain and
called the text reports "Markdown". It now executes end to end, carries its real
outputs, and is re-executed and byte-diffed by CI.

### Fixed - basis points understated by 100x

`generate_stress_report()` rendered a scenario's rate shock as `rate_shock * 100`, and
`StressScenario.summary()` rendered the raw decimal. `rate_shock` is a decimal fraction
(`0.03` == 300 bps), so the built-in scenario **named** "Rate Spike (+300 bps)" reported
`+3 bps` and `+0 bps` respectively. Both now render `+300 bps`.

This is display formatting only. No simulation input changed.

### Removed - `create_sector_specific_scenario` (breaking)

Its `sector` argument only built a display string. `create_sector_specific_scenario("small_business")`
and `create_sector_specific_scenario("commercial_real_estate")` returned objects
identical in every field except `name`, and produced byte-identical expected loss
($5,179,239.38 at `seed=7`, `n_iterations=500`).

It was removed rather than repaired. A scenario's shocks and its default-rate multiplier
are scalars, applied to **every** loan in the portfolio; giving the parameter invented
per-sector shock magnitudes would have preserved the misleading name while still shocking
the whole book.

**The missing piece is calibration, not mechanism.** The engine already resolves each
loan's sector into a per-loan baseline default rate via `SECTOR_DEFAULT_RATES`, and that
per-loan array is what the simulation scales, so a single run already carries
sector-differentiated PDs -- the 50-loan sample portfolio spans six sectors and five
distinct PDs. Segment-targeted stress would scale that existing array rather than require
a new engine. What does not exist is any primary source of CDFI-sector-specific stress
calibrations, so the per-sector factors would have been arbitrary. Anyone picking this up
should scope a calibration source, not an engine rewrite.

**Migration:** use `create_recession_scenario(...)`, which now accepts `name` and
`severity`. Do not label a scenario in a way that implies it is confined to a segment.

### Changed - `MonteCarloEngine.simulate_default_events` is now `default_probabilities` (breaking)

The old method took a `seed`, built a generator from it, and never used it; results were
identical for every seed. It performs no sampling at all - it multiplies each loan's
baseline sector default rate by the scenario multiplier and clips - so both the name and
the parameter were wrong. The `seed` parameter is gone.

Its docstring now also records that these are *not* the probabilities `run_simulation`
uses: the simulation additionally scales each path's PD by `1 + max(0, -noi_i)`.

**Migration:** `engine.simulate_default_events(scenario, seed=n)` -> `engine.default_probabilities(scenario)`.

### Added

- `MonteCarloEngine.loss_distribution` - read-only access to the losses from the most
  recent `run_simulation()`, returned as a copy. The 0.1.0 README gestured at an
  "internal loss distribution" for which no public accessor existed.
- `create_recession_scenario(..., name=..., severity=...)` - label overrides, so the
  removed sector constructor has a direct replacement.
- `CHANGELOG.md`.
- `scripts/render_readme_block.py` and `scripts/render_notebook.py` - documentation
  generators, both with a `--check` mode.
- GitHub Actions CI on Python 3.9, 3.10, 3.11 and 3.12, with actions pinned to commit
  SHAs. The package previously had no CI at all.
- A "Known limitations" section in the README.
- `README` API reference entries for `StressResult`, `STANDARD_SCENARIOS`,
  `CORRELATION_DEFAULTS`, `SECTOR_DEFAULT_RATES` and `sector_correlation_boost`, all of
  which were exported but undocumented.

### Documented, not changed - engine behaviour

Reported for transparency. **No simulation code was modified in 0.2.0.** These are
existing 0.1.0 behaviours that were previously undisclosed:

- Of the three correlated shocks drawn per Monte Carlo path (NOI, rate, property value),
  only the NOI draw affects losses. `rate_shock_i` and `prop_shock_i` are unpacked from
  the draw and then discarded. Loss-given-default is computed once from the scenario's
  *mean* property-value shock, outside the per-path loop, so it does not vary by path.
- Consequently the `correlation_matrix` constructor argument does not change the loss
  distribution. Mean expected loss over 12 seeds x 4,000 iterations on the sample
  portfolio under `2008_recession`: **$8,807,537** with the default correlations,
  **$8,804,655** with the identity matrix, **$8,814,075** with all pairwise correlations
  at +0.99 - a spread well inside the ~$54,000 across-seed standard deviation.

Whether the rate and property draws *should* feed the loss calculation is a modelling
decision rather than a bug fix, and is deliberately left for a future release.

### Fixed - `pandas` was declared and never imported

`pandas` was a declared runtime dependency in `pyproject.toml` and `setup.py`, and was
named twice in the README (*"pure numpy/pandas"*, *"Requires: numpy, pandas"*). Nothing
in the package, the scripts, the tests or the notebook ever imported it. It is removed
from all four sites; the runtime dependency is now `numpy>=1.22` alone. The floor is a
real one -- the engine uses `np.random.default_rng` -- and it is the only runtime
dependency. `tests/test_packaging.py` now fails if any declared dependency is not
imported somewhere in the package.

### Fixed - the sdist shipped a test suite that could not run

The 0.2.0 sdist omitted `tests/conftest.py`, `scripts/`, `examples/`, `.github/` and
`CHANGELOG.md`. Unpacked and run from the tarball root it gave **`6 failed, 50 passed,
1 skipped, 35 errors`**: every fixture in `conftest.py` was missing, and
`test_committed_artifact_matches_fresh_render` parametrised over
`SCRIPTS.glob("render_*.py")` with **zero** matches -- so the flagship gate did not fail,
it silently *skipped*. A `MANIFEST.in` now ships everything the suite needs, and the same
tarball gives **`93 passed`**.

CI could not have caught this: it never built a distribution. A new `sdist` job builds
both distributions, runs `twine check`, extracts the tarball and runs the shipped suite
from the tarball root, and asserts the wheel carries a licence file and classifiers.

### Fixed - no LICENSE file, and distributions with zero classifiers

MIT was asserted in the README badge, the README footer, `pyproject.toml` and `setup.py`,
and no `LICENSE` file existed in the repo, the wheel or the sdist. One is added
(`Copyright (c) 2026 Jay Patel`, matching the README footer's existing assertion) and it
now ships in both distributions.

Separately, `pyproject.toml`'s `[project]` table silently overrode `setup.py`'s eight
classifiers while declaring none of its own, so both 0.1.0 and 0.2.0 shipped wheel
METADATA with no `Classifier:` line at all. The classifiers are now declared in
`pyproject.toml`, covering every interpreter in the CI matrix.

**Known deprecation, deliberately not actioned:** `license = { text = "MIT" }` and the
`License :: OSI Approved :: MIT License` classifier are both deprecated by setuptools,
with a stated removal date of **2027-Feb-18**. Migrating to the PEP 639 form
(`license = "MIT"` plus `license-files`) would raise the build floor from
`setuptools>=61.0` to `setuptools>=77.0.0`. That floor is compatible with Python 3.9, but
raising it is a packaging decision rather than an audit fix, so it is left for a later
release. Builds warn today; nothing breaks before 2027-Feb-18.

### Fixed - invalid correlation matrices were silently accepted

`MonteCarloEngine(correlation_matrix=...)` was unchecked. A non-positive-semidefinite
matrix, and a matrix with a diagonal of 5 (not a correlation matrix at all), both produced
numbers. `is_positive_semidefinite` was exported as public API and called by nothing.

The constructor now validates shape, finiteness, symmetry, unit diagonal, entry range and
positive semi-definiteness, and `is_positive_semidefinite` is what performs the last
check. Because the matrix does not reach the loss path (see the limitation above), this
did not corrupt loss distributions -- but `apply_correlated_shocks` is public and it did
corrupt that. **This does not change the simulation math:** every matrix that was valid
before is accepted and yields identical draws; only inputs that were never correlation
matrices now raise.

### Added - gates on figures that documents hand-copy

The README quickstart has been a generated artifact since earlier in this release, but the
figures **duplicated by hand** elsewhere were ungated. Falsifying this changelog's headline
Expected Loss to `$1,111,111`, or every measured figure in README limitation 3, left the
suite fully green.

That gap is worst on the remediation path: `render_readme_block.py` without `--check`
rewrites README **in place**, so the natural response to a red golden gate silently
refreshes the generated region and leaves the hand-copied duplicates stale -- recreating
the 0.1.0 defect of two documents reporting different numbers for the same run.
`tests/test_documented_figures.py` re-derives all of them from a live run: this changelog's
comparison table, both documents' copies of the 12-seed correlation experiment, and the
`$5,179,239.38` figure quoted for the removed sector constructor.

### Added - a written mitigation for numpy stream drift

Nothing in the repo previously recorded that the golden figures depend on
`numpy.random.Generator`, whose documentation carries *"No Compatibility Guarantee ... the
bit stream may change"*, and which routes through LAPACK `gesdd`, whose singular-vector
signs are not a standardised convention across builds.

Both render scripts, the README and this changelog now state the response: **a red golden
gate after a numpy or BLAS/LAPACK upgrade with no source change means the stream moved,
and the fix is to re-render AND update every dependent document in the same commit** --
never to re-render alone. The committed figures were verified byte-identical on numpy
1.26.4 and 2.2.6, spanning the 1.x/2.x boundary. That is evidence, not a guarantee, which
is why the declared floor is `numpy>=1.22` with no upper cap: the golden gates are the
tripwire, and an unenforceable cap would only hide it.

### Fixed - prose that named things that do not exist

- `scripts/render_readme_block.py` claimed its gate lived in `tests/test_readme_artifact.py`,
  a file that has never existed. The real gate is `tests/test_committed_artifacts.py`.
- `scripts/render_notebook.py` said *"Six of its ten code cells raised."* The notebook has
  **eleven** code cells; this changelog said 11 and was right.
- `create_recession_scenario`'s load-bearing warning could be replaced by its own negation
  with the suite green. It is gated now, as is the README limitation it mirrors.

### Test suite

64 tests in 0.1.0 -> 161 in 0.2.0. The gates cover committed-artifact staleness,
notebook execution, the public API surface, version-site agreement, basis-point
rendering, the CI workflow's own action pinning and interpreter matrix, and -- added
while closing the hostile audit of this release -- declared-vs-imported dependencies,
what the sdist actually ships, licence and classifier metadata, correlation-matrix
validation, the exact values `default_probabilities` returns, and every measured figure
this changelog and the README transcribe by hand.

Two earlier gates were weaker than they read. `test_every_exported_name_appears_in_the_readme`
searched the **whole** README, so the auto-generated quickstart fence satisfied it: 10 of
the exported names could be deleted from the API Reference with the suite green, and
documented *methods* were not covered at all. It is now scoped to the API Reference
section and extended to the public methods of every documented class.

Three further gaps were found by a scoped re-audit of that work and closed.

The API-surface gate was still satisfiable by unrelated text. Scoping it to the API
Reference cut the surviving deletions from 10 to 3, but did not eliminate the class:
`expected_loss(losses)` was held up by the `StressResult(scenario, expected_loss, ...)`
field name, and the whole `Loan(...)` and `StressResult(...)` entries -- the two headline
public types -- by the trailing comments `# returns stressed Loan` and `# -> StressResult`.
Both the name gate and the member gate now anchor on the definition line (`^name(`,
`^  .member`) rather than the name appearing anywhere in the block. All 26 exported names
and every documented member now fail on deletion.

The 0.2.0 sector-scenario wording fix reached `builder.py`, README limitation 1 and this
changelog, but not the demo notebook, which still told readers the engine could not resolve
sector per loan. Nothing caught it because `scripts/render_notebook.py` executes code cells
only -- notebook markdown was gated by nothing at all, while the notebook's own summary told
readers it "cannot drift". The notebook prose is corrected, its summary now says plainly
that markdown is not executed, and a new sweep checks the README, this changelog, every
shipped and generator `.py`, and every notebook markdown cell for wordings that deny the
per-loan mechanism.

`tier1_under_stress` -- exported, README-documented and regulator-facing -- had one test,
which asserted only `isinstance(t1, float)`. Replacing its body with `return 0.1234`,
flipping `tier1_capital - stressed_loss` to `+`, hardcoding `value_at_risk(losses, 0.50)`
so the `confidence` argument was ignored, and rendering the ratio as a percentage all
shipped 144 passed. It now has hand-computed value gates, and the unused-argument sweep --
previously `MonteCarloEngine` methods and the name `seed` only -- now covers every
parameter of every exported module-level function, which is the shape of the 0.1.0
`simulate_default_events(seed=...)` defect.

## [0.1.0] - 2026-05-11

Initial release: Monte Carlo stress testing engine, correlated shock draws, VaR/CVaR
analytics, capital adequacy reporting, and a 50-loan sample portfolio generator.

See the 0.2.0 notes above before relying on anything the 0.1.0 README stated.
