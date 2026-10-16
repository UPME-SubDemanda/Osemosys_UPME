# Employment methodology review

The implementation is available locally in both repositories. The active central
build refreshes the supplied JEDI sources and applies the approved selective
LATAM productivity assumption. **The matched rooftop transfer is implemented
but pending full-precision US utility input. Published rooftop factors and all
nuclear factors are numerically unchanged.** No production SMR factor is invented.

## Observed-deployment impact

The original deployment is unchanged. Construction/manufacturing totals below
are **FTE-years associated with observed capacity commissioned in 2025-2055**,
including any construction allocated before 2025; they are not annual jobs.

| Scenario | Published factors | Source refresh only | Central with productivity policy |
|---|---:|---:|---:|
| CN | 582,914.38 | 582,900.62 | 741,209.33 |
| PA | 244,016.69 | 244,009.07 | 264,008.46 |
| PD | 212,542.95 | 212,535.46 | 232,534.85 |

The source refresh changes these totals by about -8 to -14 FTE-years. Larger
changes are driven by the new productivity assumption, not by an optimisation
change. `change_attribution.csv` separates the source refresh and productivity
effects for each scenario, region, technology, year and output variable. The
maximum reconciliation residual from independently rounded 12-significant-digit
CSV fields is about 0.000001 FTE/FTE-year, within serialization precision.

`central/`, `low/`, `high/` and `source-refresh/` each contain factor and employment
comparisons, construction-cohort totals, solar ratios and provenance. The low/high
productivity cases use 0.33/0.30 (central 0.32); these are screening assumptions,
not confidence limits. The comparison retains all three factor categories, while
runtime employment results remain Direct only. Nuclear/SMR ratios cannot be
reported because no separate supported SMR factor exists.

The input is the preserved `RawResultsLong` sheet: 5,814 rows, of which 2,999
capacity cells are blank. These are disclosed in each case's
`unobserved_capacity_cells.csv`, not replaced by zero. Results describe the same
observed cells in both replays. Original scenario exports are unavailable, so
original solver-output completeness cannot be independently verified. The
comparison has 3,052 matched derived employment rows per case. Regional mapping
coverage is tested separately; both replays use the corrected mapping.

## Validation

- Factor repository: **39 tests passed**.
- Backend employment/comparison and existing regional suites: **72 tests passed**.
- Four generated CSVs rebuild byte-for-byte and match the four packaged CSVs.
- Source/input/output hashes and low/central/high ordering pass.
- Both native source workbook hashes are unchanged; existing staged additions
  and working-tree modifications remain unstaged by this implementation.
- The strict `--require-solar-ratios` gate rejects the missing utility input
  before changing model outputs.
- The workbook-report script completed against the preserved input: 887 component
  rows, 877 aggregated rows, zero missing mapping/factor diagnostics. It produces
  its six base sheets, not the additional manually maintained baseline pivots.
- Native Excel recalculation/visual rendering and full Docker/frontend CI were
  not performed. CSV numerical calculations are authoritative for this review.

`validation.json` records the data checks, hashes and serialization tolerance.
Reproduce generation and comparisons using
`../../docs/EMPLOYMENT_FACTORS.md`. For an independent build verification:

```sh
# In the factor repository, choose a separate writable review directory:
python scripts/build_employment_factors.py --output-dir <review-directory>
# In OSeMOSYS_UPME:
python backend/scripts/validate_employment_factor_delivery.py --source-repo ../colombia-employment-factors --rebuild-dir <review-directory>
```

The runtime dependency pins published source/artifact commit
`f46e8b480f965e68bd4d5734e5e9ab708af593a7`. The snapshot manifest separately
records input/code commit `e1dcd8328f197608c2b7dc3d5b9c29cd7d031324`, its content
hashes and the generated-data checksums. Its dirty flag describes the build-time
working tree, including generated artifacts awaiting their separate commit;
the methodology inputs are committed. This avoids self-referencing commit SHAs.

## Remaining inputs and handover

Provide the six full-precision utility results and matching saved settings at
the configured source path (or update that path in policy). The extractor will
validate the matched run, the builder will derive the six rooftop factors and
their future series, and the existing tests/comparisons can be rerun. No extra
GDP multiplier is applied to the Colombia anchor or derived rooftop factors.

SMR factor work additionally needs the reactor/module/site definition and
compatible construction/staffing evidence. Current generic nuclear values remain
unchanged meanwhile. Draft English PR text, delivery steps and a Spanish UPME
explanation are in `../../docs/EMPLOYMENT_PR_UPDATE_DRAFT.md`. This delivery uses
separate commits for source snapshots, methodology, generated factors, runtime
integration, reporting and handover. It does not edit the PR description/comments
or rerun optimisation.
