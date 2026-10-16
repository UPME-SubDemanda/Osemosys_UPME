# Draft update for PR #174 — not published

Verified PR source before this publication: `DEA-GE/Osemosys_UPME:employment-factors`
(`cf98432c318bb2d93bc54b6dcddac1f15bd5ed2d`). Target:
`UPME-SubDemanda/Osemosys_UPME:develop`. Recheck the live PR state, head/base,
reviews, discussions and branch protection before publishing. If closed/merged,
open a follow-up PR from a new approved branch instead of assuming #174 is
updatable. PR #174 was open and unmerged at verification. The authorised source
branch push updates its code; this draft description and PR comments remain
unpublished.

## Proposed title

Make employment factors traceable and apply selective LATAM productivity assumptions

## Draft description

Employment remains an ex-post calculation on unchanged model deployments.
The factor-source pipeline now extracts the supplied saved JEDI inputs,
preserves original workbooks, and records source settings, cell references and
checksums. A six-ratio residential/utility transfer is implemented and tested,
separately by construction/O&M and Direct/Indirect/Induced categories.

The saved utility run is still missing, so the runtime deliberately retains the
published rooftop factors with an explicit pending-input label. No rounded
screenshot values or desired technology rankings are used as factor inputs.
The historical rooftop `9328` display error is corrected in curated inputs;
Python already consumed its normalised numeric field. Refreshing the newly
provided US run is a separate source-data change.

The selected LATAM/OECD productivity ratio 0.32 (inverse 3.125) is implemented
as a configurable modelling assumption with technology/phase eligibility.
Colombia I-JEDI, already-regional values, global manufacturing, bioenergy and
nuclear O&M are excluded. Original source series remain available. Low/high
cases and a source-refresh-only reference separate assumption impacts from
source refreshes. Nuclear factors are unchanged pending a supported SMR
definition and evidence.

The backend uses a checksum-verified data snapshot with a pinned package API
revision. It records source-content provenance in persisted employment rows,
maps all seven regional prefixes, rejects duplicate/invalid factors, and
supports replay of the preserved RawResultsLong inputs without a new solve.

Validation and impact evidence live under
`backend/reports/employment_methodology/`; units distinguish construction
FTE-years from recurring annual O&M FTE. Blank original export cells are
disclosed rather than filled with zero. See the methodology documentation for
commands, limitations and rollback.

## Delivery sequence

- Resolve the full-precision utility input before claiming the rooftop transfer is active.
- Review source inputs, policy, generated factors and separate sensitivity effects.
- Source snapshots, methodology and generated artifacts are separate commits.
  Input/code revision is `e1dcd8328f197608c2b7dc3d5b9c29cd7d031324`; the published
  artifact/dependency revision is `f46e8b480f965e68bd4d5734e5e9ab708af593a7`.
  The native workbooks were committed from their verified latest working-tree
  versions, rather than their older pre-existing staged copies.
- The package dependency pins the published artifact commit; generated-data
  checksums and the distinct input/code provenance remain consistent.
- Recheck upstream changes; handle conflicts in a reviewed integration step without
  resets or force pushes. Preserve unrelated/staged workbook work.
- Run source tests and deterministic regeneration; backend employment/regional tests;
  then the PR's existing Validate And Build checks (Compose validation, frontend
  typecheck/build, backend tests and image builds). Local Docker/CI was not invoked
  merely to change these ex-post factors.
- Push the authorised commits to the verified PR head. Publishing this description
  or comments remains a separate action. Roll back using revert changes and the
  prior source/snapshot version.

## Explicación para UPME

Se corrigió una inconsistencia de escala en el campo original de solar
residencial; el cálculo en Python ya utilizaba el valor normalizado. Los nuevos
archivos permiten actualizar los datos de origen y documentar su trazabilidad.
Se implementó un método que aplica relaciones entre solar residencial y de gran
escala calculadas con el mismo US-JEDI al factor de referencia de I-JEDI Colombia,
separando construcción y O&M y conservando categorías sencillas de empleo.

Faltan los resultados de gran escala con precisión completa. Por ello, todavía
se conservan los factores publicados de solar residencial y se identifica esta
limitación explícitamente. No se han utilizado los valores redondeados de las
imágenes para fijar los nuevos factores.

El cociente de productividad 0,32 se incorpora como supuesto, no como una nueva
estimación estadística reproducida. Su inverso exacto es 3,125. Se aplica solo
a fases elegibles de fuentes OECD, evitando repetir ajustes en I-JEDI Colombia
o en factores que ya representan LATAM. La cobertura de empleo directo difiere
entre los dos modelos JEDI y la transferencia sigue siendo aproximada.

Los cambios en empleo se evalúan con la misma expansión energética, sin volver
a optimizar el modelo. Los factores nucleares permanecen sin cambios; no se
impone un aumento arbitrario para los SMR. Los resultados de construcción se
interpretan como años-persona equivalentes a tiempo completo y los de O&M como
empleo anual, manteniendo explícitas las incertidumbres y las convenciones.
