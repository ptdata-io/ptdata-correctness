# ptdata — correctness

**A runnable, public test suite you can execute against the live ptdata service to verify
that it behaves exactly as the [methodology](https://github.com/ptdata-io/ptdata-methodology)
documents.**

Point-in-time data is only trustworthy if its claims are *falsifiable*. Every test here is a
golden file — a specific, historically-grounded claim ("Lehman was in the S&P 500 on
2008-09-15 and not on 2008-09-16"; "GE's FY2017 figures as known on 2018-02-28 are the
original, not the restated") — that either passes against the live service or fails visibly.
If we are wrong, these go red.

## Quick start

```bash
git clone https://github.com/ptdata-io/ptdata-correctness
cd ptdata-correctness
pip install -r requirements.txt

# Point at the live service (or your own local server).
export PTDATA_BASE_URL="https://api.ptdata.io"   # default: http://localhost:8000
# Free tier is open (IP rate-limited). Optional paid key:
# export PTDATA_API_KEY="ptd_…"   # sent as Authorization: Bearer

pytest -v
```

Cases that are out of the current product scope — raw-price corporate actions, options-implied
expected move (see [methodology limitations](https://github.com/ptdata-io/ptdata-methodology/blob/main/docs/08-known-limitations.md))
— carry a `skip:` reason and report as **SKIPPED**, never a silent or vacuous green. In-scope
cases are the specification: if the service is wrong, they go **RED**.

**Live baseline (2026-07-23 against `https://api.ptdata.io`):** **12 passed, 6 skipped, 0 failed**.

**Confidence index on parsed facts.** Fundamentals below the XBRL era (~pre-2009) come from a
labeled **parsed tier**: each value carries `provenance` (`xbrl` | `parsed`) and, for parsed
values, an `extraction_confidence` of `verified` | `high` | `medium` — returned on every response
so you can filter or weight by trust. Nothing is published below those tiers (conflicting or
unverified extractions are withheld). The `enron_2001_q3_10q` and `worldcom_2002_10q` cases assert
parsed values directly. Definitions: [docs/09-pre-xbrl-fundamentals.md](https://github.com/ptdata-io/ptdata-methodology/blob/main/docs/09-pre-xbrl-fundamentals.md).

## How it works

- `cases/<category>/*.yaml` — the golden files. Each names a tool, the request parameters, a
  provenance note explaining the historical context, and a list of expectations. Some cases
  are multi-step (two `as_of` dates) to demonstrate point-in-time divergence directly.
- `tests/test_<category>.py` — thin, data-driven runners that load every case in a category
  and assert the live response matches.
- `conftest.py` — the HTTP client and the assertion engine (operators: `eq`, `approx`, `lt`,
  `gt`, `contains`, `not_contains`, `exists`, `absent`, plus cross-step comparisons).

## Categories

| Category | What it pins | Status |
|---|---|---|
| `fundamentals` | As-reported vs. restated, point-in-time (XBRL + labeled parsed tier) | **active** (GE as-of original; Enron Q3-2001 + WorldCom Q1-2002 via parsed tier; GE restatement case skipped — no headline FY2017 restatement in companyfacts) |
| `index_membership` | Survivorship-free index membership | **active** (SP500: Lehman, Tesla; DJIA: Apple 2015 / GE 2018; NDX DASH 2024; DJT UBER 2024; DJU Vistra 2024) |
| `filing_lineage` | Amendment chains via accession linkage | **active** (GE FY2005 10-K/A) |
| `earnings_events` | 8-K timestamps + as-reported figures | **active** timestamp case; beat/miss vs implied skipped (options, 6f) |
| `corporate_actions` | Point-in-time split/spinoff adjustment | skipped (raw prices out of redistributable scope) |
| `implied_expectation` | Point-in-time options-implied expected move | skipped (options data not live yet) |

## Contributing

**PRs with new edge cases are welcome and encouraged.** A good case is a specific historical
claim with a clear provenance note and verifiable expected values. Add a YAML file under the
right `cases/` subdirectory — no code change needed — and open a PR. Edge cases that expose a
real correctness gap are the most valuable contribution you can make to this project.

## License

[MIT](LICENSE).
