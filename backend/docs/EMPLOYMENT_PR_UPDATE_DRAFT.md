# Draft update for PR #174 — not published

## Calibrate MW-scale PCH employment and classify the existing nuclear technology as SMR

PR source: `DEA-GE/Osemosys_UPME:employment-factors`; target:
`UPME-SubDemanda/Osemosys_UPME:develop`. Pre-change head verified as
`348da285030c2233e79281ffac72306d1b76ce21`.

The existing `PWRNUC` generating technology represents SMR. Its employment
mapping now resolves to the distinct `SMR` catalogue entry, with constant
conventional-nuclear OECD proxies: 11.8 construction, 1.3 manufacturing and
0.6 O&M. Combined C+M is 13.1 FTE-years/MW. Employment timing uses the Colombian
SMR datasheet's 2030 assumptions: 40-year lifetime and 8-year construction.

`PWRHYDROR_NDC` uses the analyst-calibrated MW-scale small-hydro source:
7.36 construction, 2.30 manufacturing and 0.8 O&M in 2024, with subsequent
small-RoR catalogue cost scaling. `PWRHYDROR` now uses existing large hydro.
These classifications follow catalogue cost correspondence and project-team
approval; dispatch status alone does not establish plant scale. The seven
existing regional prefixes inherit the same corrections.

The canonical artifact is pinned at
`a0aed31f75844cc1af32e67318de5037b3f46f9d` in
`DEA-GE/colombia-employment-factors`. The targeted snapshot refresh preserves
all unrelated baseline rows and assumptions, including all wind and rooftop
choices. Conventional Nuclear remains available. The energy model's codes,
costs, capacity, efficiency, lifetime, activity, equations and seven existing
employment output contracts are unchanged.

The baseline used higher Latin America nuclear factors (19.6/1.3/1.15), so
SMR numerical changes are expected. This is not an arbitrary SMR uplift.
The old PR PCH O&M was 15.955625 in 2024: interpolated 5.1058 multiplied by
3.125. The new calibrated source does not receive either adjustment.

Validation: 60 source tests and 37 downstream employment tests pass. Five
canonical CSVs reproduce exactly; wind and unrelated factor rows are unchanged.
The full backend suite cannot collect nine modules on Windows because they
import Unix-only `resource`; no unrelated platform changes are included.

See `backend/docs/EMPLOYMENT_FACTORS.md` and
`backend/reports/employment_methodology/pch-smr/` for evidence, reproduction
commands, source/mapping comparisons and limitations. This draft does not
publish a PR comment or modify the PR description.
