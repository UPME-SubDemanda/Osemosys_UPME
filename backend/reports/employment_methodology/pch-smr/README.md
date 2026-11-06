# PCH/SMR delivery evidence for PR #174

## Repositories and integration

- Canonical: [DEA-GE/colombia-employment-factors](https://github.com/DEA-GE/colombia-employment-factors),
  branch `pch-smr-employment-factors`, artifact commit
  `a0aed31f75844cc1af32e67318de5037b3f46f9d`.
- Implementation commits: `8fa7e48` (catalogue/methodology/tests) and
  `ac165f7` (reproducible source-refresh publication).
- Integration: `DEA-GE/Osemosys_UPME:employment-factors` ->
  `UPME-SubDemanda/Osemosys_UPME:develop`,
  [existing PR #174](https://github.com/UPME-SubDemanda/Osemosys_UPME/pull/174).
- The preserved baseline is PR head
  `348da285030c2233e79281ffac72306d1b76ce21`. The runtime dependency is pinned
  to the canonical artifact above; no moving package branch is used.
- No force push, merge or duplicate PR is part of this delivery.

## Changes and accounting boundary

The source repository adds the calibrated PCH source under existing Hydro
(small), adds separate SMR source observations and defaults, derives combined
C+M once, keeps SMR coefficients constant, and extracts SMR employment timing
from the catalogue's 2030 D10/D11 cells. The five packaged CSVs, maintained
scenario exports and provenance are regenerated. Tests and existing methodology
documentation describe each reported value, calculation and analyst assumption.

The integration changes the three agreed mappings, regenerates the targeted
runtime snapshot and adds regression tests, comparison support and evidence.
Only the optional baseline-assumption path and additive targeted-refresh
provenance extend internal service interfaces. All seven employment output
names, units and capacity conventions remain compatible. Energy model
technology codes, capacity, costs, efficiency, operational lifetime, activity,
equations and solver behaviour are unchanged.

C/M/C+M coefficients are FTE-years per MW of additions. O&M is annual FTE per MW
of operational capacity. C+M includes manufacturing once with the established
full regional hydro/nuclear boundary; it is not added to separate C and M.
Downstream operational capacity is surviving model-period new-build stock.
The boundary does not prove full Colombian local content.

## Raw and effective coefficients

C = construction/installation; M = manufacturing. All rows are Direct.

| Source/category | Raw C | Raw M | Raw C+M | Raw O&M | PR effective 2024 C | PR effective 2024 M | PR effective 2024 C+M | PR effective 2024 O&M |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hydro-small / Rutovitz 2015, old selective PR | 15.8 | 10.9 | 26.7 | 4.9 | 51.44875 | 11.3578 | 62.80655 | 15.955625 |
| MW-scale PCH / calibrated | 7.36 | 2.30 | 9.66 | 0.8 | 7.36 | 2.30 | 9.66 | 0.8 |
| Conventional Nuclear / retained Latin America selection | 19.6 | 1.3 | 20.9 | 1.15 | 19.6 | 1.3 | 20.9 | 1.15 |
| SMR / conventional nuclear OECD proxy | 11.8 | 1.3 | 13.1 | 0.6 | 11.8 | 1.3 | 13.1 | 0.6 |

The unadjusted legacy annual 2024 small-hydro coefficients are
16.4636/11.3578/27.8214/5.1058 for C/M/C+M/O&M. The old 5.1058 arises from
linear interpolation of 4.9 toward a 7% increase by 2030. The older PR snapshot
additionally multiplies construction and O&M by 3.125. Manufacturing is not
scaled by that multiplier. The new calibrated PCH source avoids both uplifts;
its later O&M is 0.798796992481 in 2030 and 0.793984962406 in 2050-2055 under
ordinary catalogue OPEX scaling. New SMR factors are constant through 2055.

The source name `ESMAP 2023 + Rutovitz 2025 (MW-scale PCH calibrated)` does
not attribute every coefficient to ESMAP. Its 0.8 is an analyst assumption;
7.36 and 2.30 are generic-hydro literature proxies.

## Exact mapping corrections

| Existing OSeMOSYS code | Old employment category | New category/source |
| --- | --- | --- |
| PWRHYDROR | Hydro (small) | Hydro (large), existing selective source |
| PWRHYDROR_NDC | Hydro (small), legacy selective source | Hydro (small), MW-scale calibrated source |
| PWRNUC | Nuclear | SMR, Rutovitz 2015 conventional-nuclear proxy |

The same corrections apply to AN_, CA_, IN_, NE_, OR_, SE_ and SO_ prefixed
variants. Existing PWRNUC is reassigned **Nuclear -> SMR**; no new nuclear
generating code is created. Its employment assumptions are 40-year lifetime
and 8-year construction, from the 2030 SMR catalogue, rather than PWR 60/7.4.

Hydro classification follows project-team approval and model-cost correspondence
to the large/small RoR catalogue sheets. NDC status alone does not establish
micro/mini scale. PEN distinguishes 1-20 MW small hydro from <1 MW mini hydro;
individual plant sizes have not all been verified. PWRHYDDAM and wind mappings
remain unchanged.

## Numerical effects under identical observed deployment

The existing Latin America Nuclear source differs numerically from the OECD
benchmark selected for SMR. Thus this implementation changes SMR employment
outputs, while preserving conventional Nuclear as an independent catalogue entry.

| Affected deployment | Metric | Before | After |
| --- | --- | ---: | ---: |
| CN, PWRHYDROR_NDC | C+M cohorts commissioned 2025-2055, FTE-years | 247,757.89 | 37,042.92 |
| CN, PWRHYDROR_NDC | Annual O&M in 2055, FTE | 62,787.37 | 3,061.11 |
| PA, PWRNUC | C+M cohorts commissioned 2025-2055, FTE-years | 5,948.75 | 3,948.56 |
| PA, PWRNUC | Annual O&M in 2055, FTE | 326.41 | 180.85 |

Total observed construction-cohort FTE-years across technologies change from
741,209.33 to 530,494.36 in CN, 264,008.46 to 262,008.27 in PA, and remain
232,534.85 in PD. These are job-years for commissioning cohorts, not annual jobs.

The supplied workbook has no observed new-build deployment for PWRHYDROR in
these comparisons; its factor/mapping correction is nevertheless covered by
the annual coefficient comparison and mapping tests. Missing exported capacity
cells are not evidence of zero capacity: 2,999 blank cells are excluded in both
replays. Original scenario exports would be needed to establish completeness.

## Validation

- 60 source tests and 37 downstream employment tests passed.
- Five canonical CSVs, three runtime files and nine comparison files reproduce.
- 2,624 unrelated runtime factor rows remain identical in every field.
- 830 observed wind employment rows and 2,877 unrelated employment rows are
  numerically unchanged. All source wind factors/references/projections are
  unchanged; source audit evidence is in the canonical repository.
- There are 128 changed existing factor rows, 128 new SMR factor rows and no
  removed catalogue technologies. No duplicate or missing phase/year keys.
- All eight mapped variants of PWRNUC resolve to SMR and none to Nuclear.
- Construction/manufacturing is combined once; new/operational capacity and
  annual FTE/cumulative FTE-years retain their existing definitions.
- Full backend collection is blocked on Windows by nine existing modules
  importing the Unix-only `resource` module. No unrelated platform refactoring
  is included. This delivery does not claim a fully passing backend suite.
- Exact checks, hashes and numerical comparisons are in
  [validation.json](validation.json), [mapping_factor_comparison.csv](mapping_factor_comparison.csv),
  [affected_employment_summary.csv](affected_employment_summary.csv) and
  [comparison_provenance.json](comparison_provenance.json).
- Reproduction commands are in [EMPLOYMENT_FACTORS.md](../../../docs/EMPLOYMENT_FACTORS.md).
  The preserved workbook and historical report directories remain unchanged.

## Scientific limitations and references

PCH O&M 0.8 and the 0.3/0.8/1.5 provisional sensitivity bounds are analyst
calibrations, not directly reported ESMAP coefficients. Only base is executable.
Rusumo is an 80-MW benchmark outside the PEN 1-20 MW class. Generic hydro C/M
and conventional-nuclear SMR proxies need Colombian project/design validation.
SMR-specific factory/onsite boundaries, design, deployment scale, FOAK/NOAK
staffing and local supply chains may produce different future factors.

- Rutovitz, J., Dominish, E., & Downes, J. (2015).
  [Calculating Global Energy Sector Jobs: 2015 Methodology Update](https://opus.lib.uts.edu.au/bitstream/10453/43718/1/Rutovitzetal2015Calculatingglobalenergysectorjobsmethodology.pdf).
  ISF, University of Technology Sydney. Table 1 p.5: OECD hydro/nuclear
  benchmarks; Table 2 p.8: retained Latin America nuclear selection.
- Rutovitz, J., Langdon, R., Briggs, C., Mey, F., Dominish, E., & Nagrath, K.
  (2025). [Updated employment factors and occupational shares for the energy
  transition](https://doi.org/10.1016/j.rser.2025.115339).
  Renewable and Sustainable Energy Reviews, 212, 115339. Table 3 p.4:
  generic hydro C=7.36, total M=2.30; generic O&M=0.14 is not selected for PCH.
- ESMAP / World Bank (2023). [Jobs Generated by the Regional Rusumo Falls
  Hydroelectric Project: Job Creation Potential of the Clean Energy Transition](https://documents1.worldbank.org/curated/en/099012324075512707/pdf/P1764381b7d6840311ba351545ad17ca2a4.pdf).
  Approximately 50 forecast workers/80 MW gives calculated 0.625 employees/MW;
  detailed forecasts are 51 full-time staff. See pp.x-xi, p.25, Table 8 and Figure 14.
- IRENA (2023). [Renewable Energy Benefits: Leveraging Local Capacity for
  Small-Scale Hydropower](https://www.irena.org/-/media/Files/IRENA/Agency/Publication/2023/Sep/IRENA_Leveraging_small_scale_hydropower_2023.pdf).
  Figure 11/Table 5 pp.35-36 provide scale-dependent labour evidence.
- OECD NEA / IAEA (2018). [Measuring Employment Generated by the Nuclear
  Power Sector](https://doi.org/10.1787/9789264305960-en).
  Conventional nuclear context; not SMR-specific validation.
- UPME (2026). [PEN Tomo II 2025-2055](https://docs.upme.gov.co/DemandayEficiencia/Documents/PEN_2025_2055/PEN_Tomo_II-Conceptualizacion_de_escenarios_PEN_2025-2055_VF.pdf),
  p.69, and [parameterisation strategy](https://docs.upme.gov.co/DemandayEficiencia/Documents/PEN_2025_2055/Estrategia_de_parametrizacion_para_la_construccion_de_escenarios_del_PEN_2025-2055VrF.pdf),
  Table 12 pp.67-68 and pp.69-72. See preserved Colombian Technology Catalogue
  sheets 5.a/5.b/5.c and 13.b; the catalogue's 2030 SMR D10/D11 cells provide 40/8.
