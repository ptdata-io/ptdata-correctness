# ptdata — correctness

**A runnable, public test suite you can execute against the live ptdata service to verify
that it behaves exactly as the [methodology](https://github.com/ptdata/ptdata-methodology)
documents.**

Point-in-time data is only trustworthy if its claims are *falsifiable*. Every test here is a
golden file — a specific, historically-grounded claim ("Lehman was in the S&P 500 on
2008-09-14 and not on 2008-09-22"; "GE's FY2017 figures as known on 2018-02-28 are the
original, not the restated") — that either passes against the live service or fails visibly.
If we are wrong, these go red.

## Quick start

```bash
git clone https://github.com/ptdata/ptdata-correctness
cd ptdata-correctness
pip install -r requirements.txt

# Point at the service. Use the public endpoint, or your own local dev server.
export PTDATA_BASE_URL="https://api.ptdata.example"   # default: http://localhost:8000
export PTDATA_API_KEY="ptk_..."                        # free key; omit if not required

pytest -v
```

Until the service implements a given behavior, that test is **RED** — and that is correct.
The golden files are the specification; the implementation chases them green.

## How it works

- `cases/<category>/*.yaml` — the golden files. Each names a tool, the request parameters, a
  provenance note explaining the historical context, and a list of expectations. Some cases
  are multi-step (two `as_of` dates) to demonstrate point-in-time divergence directly.
- `tests/test_<category>.py` — thin, data-driven runners that load every case in a category
  and assert the live response matches.
- `conftest.py` — the HTTP client and the assertion engine (operators: `eq`, `approx`, `lt`,
  `gt`, `contains`, `not_contains`, `exists`, `absent`, plus cross-step comparisons).

## Categories

| Category | What it pins |
|---|---|
| `fundamentals` | As-reported vs. restated, point-in-time (Enron, GE, WorldCom) |
| `corporate_actions` | Point-in-time split/spinoff adjustment with metadata (AAPL 7-for-1) |
| `index_membership` | Survivorship-free S&P 500 membership (Lehman, Tesla) |
| `filing_lineage` | Amendment chains via accession linkage |
| `earnings_events` | 8-K timestamps, as-reported figures, realized vs. options-implied move |
| `implied_expectation` | Point-in-time options-implied expected move (divergence across as_of dates) |

## Contributing

**PRs with new edge cases are welcome and encouraged.** A good case is a specific historical
claim with a clear provenance note and verifiable expected values. Add a YAML file under the
right `cases/` subdirectory — no code change needed — and open a PR. Edge cases that expose a
real correctness gap are the most valuable contribution you can make to this project.

## License

[MIT](LICENSE).
