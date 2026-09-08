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

It was removed rather than repaired. The engine applies a scenario's shocks to **every**
loan in the portfolio; there is no mechanism to stress one sector and spare another.
Giving the parameter invented per-sector shock magnitudes would have preserved the
misleading name while still shocking the whole book, and there is no primary source of
CDFI-sector-specific stress calibrations that would have made such numbers anything
other than arbitrary.

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

### Test suite

64 tests in 0.1.0 -> 93 in 0.2.0. The new gates cover committed-artifact staleness,
notebook execution, the public API surface, version-site agreement, basis-point
rendering, and the CI workflow's own action pinning and interpreter matrix.

## [0.1.0] - 2026-05-11

Initial release: Monte Carlo stress testing engine, correlated shock draws, VaR/CVaR
analytics, capital adequacy reporting, and a 50-loan sample portfolio generator.

See the 0.2.0 notes above before relying on anything the 0.1.0 README stated.
