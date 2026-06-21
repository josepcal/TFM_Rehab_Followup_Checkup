# Tasks: Sustained Phonation Analysis Function (`sustained_phonation_v1`, UC-04)

> **Revised:** reflects wrapping the vendored `analyze_sustained_vowel` instead of
> writing librosa logic from scratch. Net effect: less signal-processing code to write,
> more integration/dependency work (vendoring, new deps, fixture-driven failure-mode testing).

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 250-400 (incl. ~620-line vendored file counted as a single low-risk addition) |
| 400-line budget risk | Medium — mainly from vendoring the whole script in one PR |
| Chained PRs recommended | Optional |
| Suggested split | PR #1: vendor file + adapter + deps/Dockerfile → PR #2: metric_definition seed + tests |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain (only if PR #1 alone exceeds the 400-line budget after counting the vendored file) |

Decision needed before apply: Yes — same two open questions as before (degenerate-input failure mode, `metric_definition` domain grouping), plus: confirm vendoring the *entire* `dysarthria_analysis.py` is acceptable from a licensing/ownership standpoint before it lands in the repo.
Chained PRs recommended: Optional
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Vendor `dysarthria_analysis.py` + add dependencies | PR 1 | Pure addition, no FTM logic yet; review focuses on "does this file match the upload," not line-by-line. |
| 2 | Adapter (`voice.py`) + error type | PR 1 | The only genuinely new FTM code in this slice. |
| 3 | `metric_definition` seed (5 rows) | PR 2 | Split out if PR 1 is already large after the vendored file. |
| 4 | Fixtures + tests, including the degenerate-input failure-mode probe | PR 2 | The PraatError-vs-NaN determination (task 2.4 below) should happen early — it gates the adapter's exact guard logic. |

## Phase 1: Confirm Open Questions Before Implementation

- [x] 1.1 Confirm vendoring the full `dysarthria_analysis.py` is acceptable (ownership/license, given it was supplied directly rather than pulled from a package registry).
- [x] 1.2 Confirm exercise #1's `analysis_setup` row points at `"sustained_phonation_v1"` (per FTM plan §12 step 6; carried over from the original D9 scope, unaffected by this revision).
- [x] 1.3 Decide whether `metric_definition` needs a `domain` field to separate `phonation_duration_sec` (respiratory_support) from the other four metrics (voice_stability) — get product/clinical input; if deferred, document the flat-weight model as a known simplification.
- [ ] 1.4 Decide timing for adding `ffmpeg` to the worker image: this slice (D9) or D10's hardening pass.

### Phase 1 — Execution Prompts

Each prompt below is self-contained: an executor (human or agent) should be able to run it without reading the rest of this repo's chat history. Paste one at a time.

#### Prompt 1.1 — Vendoring license/ownership check

```
OBJECTIVE
Determine whether `dysarthria_analysis.py` may be vendored into the FTM repo at
`api/app/analysis/vendor/dysarthria_analysis.py`, and on what terms.

CONTEXT
- The file was supplied directly (not pulled from PyPI or another package registry)
  for the FTM project's `sustained_phonation_v1` analysis function (UC-04, D9).
- Its docstring header (top ~21 lines) describes purpose and recording protocol only —
  no SPDX line, license, copyright, or author attribution is present.
- ADR-0008 ("Extracción de métricas agnóstica") requires technician-authored analysis
  functions to be "deployed with the codebase via PR + review" — this implies the repo
  needs clear provenance for any vendored code, not just working code.
- This is an authorization question, not a technical one — do not infer permission
  from the absence of a license notice.

STEPS
1. Open `dysarthria_analysis.py` and confirm there is still no license/author header
   (re-check in case the copy you have differs from the one referenced here).
2. If no license/attribution is present, do NOT proceed to vendor the file. Stop and
   ask: "Who authored dysarthria_analysis.py, and is the FTM team authorized to include
   it in this repository (e.g. internal work product, MIT-licensed personal script,
   third-party tool with permission)?"
3. Once an answer is given, draft a one-line attribution header to prepend to the
   vendored file, e.g.:
     # Vendored from <source>, <date>. Included with permission of <author/owner>.
4. Record the answer and the agreed header line in this tasks.md file under task 1.1.

OUTPUT
A short note in this file: who owns/authored the script, the terms under which it's
included, and the exact attribution header text to use when Phase 2 vendors the file.
This task blocks Phase 2 (vendoring) — do not start Phase 2 until this is resolved.
```

#### Prompt 1.2 — Confirm `analysis_setup` seed row and column name

```
OBJECTIVE
Verify, against the actual repository (not assumptions from prior docs), the real
column name on `analysis_setup` that references a registered analysis function by
name, and confirm exercise #1's seed row already points it at
"sustained_phonation_v1".

CONTEXT
- There is a known terminology mismatch between two existing docs: ADR-0008 names the
  column `metric_api_endpoint`; the D8 design doc (`openspec/design/analysis-registry-worker-uc6.md`)
  calls it `analysis_setup.function_name`. Both describe the same concept — "the name
  the worker resolves in the registry" — but only one is the real column name.
- ADR-0017 states `ftm_schema.sql` is the SQL-first source of truth for the schema,
  with `models.py` mirrored by hand.
- Per the FTM implementation plan §12 step 6, the D1 migration was meant to include
  "seed de los 3 ejercicios + analysis_setup con function_name" (or whatever the real
  column is) — exercise #1 ("Fonación sostenida") should already reference
  `sustained_phonation_v1`.

STEPS
1. Search the repo for the `analysis_setup` table definition — check `ftm_schema.sql`
   first (source of truth per ADR-0017), then `api/app/**/models.py` for the
   SQLAlchemy mirror. Note the exact column name used for the function reference.
2. Search migrations/seed data (`api/migrations/`) for the exercise #1 seed row and
   confirm its function-reference column currently equals "sustained_phonation_v1".
3. If the real column name differs from what either `openspec/design/analysis-registry-worker-uc6.md`
   or `openspec/design/sustained-phonation-v1-uc4.md` currently says, update the stale
   doc(s) to match reality — do not leave both terms floating as if interchangeable.
4. If the seed row is missing, empty, or pointing at the wrong name, do NOT fix it
   as a side effect of this verification task. Flag it explicitly and route the fix
   through Phase 4 (`metric_definition` seed work) or a separate ticket, since seed
   data changes deserve their own review.

OUTPUT
A short note recording: (a) the confirmed real column name on `analysis_setup`,
(b) the exact file/line where exercise #1's seed row lives, and (c) whether it
currently resolves to "sustained_phonation_v1" correctly.
```

#### Prompt 1.3 — `metric_definition` domain-grouping decision

```
OBJECTIVE
Get a decision on whether `metric_definition` needs a new `domain` (or similar
grouping) field, given that `sustained_phonation_v1` returns five metrics that span
two distinct clinical constructs.

CONTEXT
- `sustained_phonation_v1` (via the vendored `analyze_sustained_vowel`) returns:
  `phonation_duration_sec`, `jitter_local_pct`, `shimmer_local_pct`, `hnr_db`,
  `volume_std_db`.
- The vendored script's own (NOT wired into FTM — see the Explore doc's Decision)
  `score_domains()` function groups these as: `phonation_duration_sec` ->
  "respiratory_support"; the other four -> "voice_stability". This grouping is
  clinically meaningful even though FTM deliberately does not reuse that scoring code.
- The current `metric_definition` schema (per ADR-0008) is: metric_key, label, unit,
  weight — a flat list with no grouping concept.
- This is a product/clinical decision, not a purely technical one (same category as
  ADR-0012 and ADR-0019, both marked "Pendiente PO" in the ADR log) — the executor
  should seek sign-off rather than decide unilaterally.

STEPS
1. Prepare a short decision brief (2-3 sentences) stating the question and these two
   concrete options:
     (a) Add a `domain` column to `metric_definition` now, populate it for these five
         rows, and use flat weight-within-domain rather than one global weight.
     (b) Keep `metric_definition` flat (current design: 5 rows, weight 0.2 each) and
         treat domain grouping as a later, separate concern (e.g. handled entirely in
         the LLM insight `criteria` payload or in `reporting`, not in the data model).
2. Present the brief to the product owner / clinical lead for a decision.
3. If no answer is available within this task's timebox, apply option (b) as the
   documented MVP default — this is already what `openspec/design/sustained-phonation-v1-uc4.md`
   currently specifies — and explicitly record it as a known simplification rather
   than a closed decision, so it surfaces again later rather than being forgotten.
4. Do not invent specific domain-weighting numbers without a traceable source
   (clinical guidance, or an explicit "engineering default, revisit later" label).

OUTPUT
Either: a recorded decision (with who approved it and the resulting schema/seed
change), or a recorded "default (b) applied, pending PO input" note — added to
`openspec/explore/sustained-phonation-v1-uc4.md`'s Open Questions section and this
tasks.md file.
```

#### Prompt 1.4 — `ffmpeg` timing decision

```
OBJECTIVE
Decide whether to add the `ffmpeg` binary to the worker Docker image in this slice
(D9) or defer it to D10's recording-validation hardening pass.

CONTEXT
- `ensure_pcm_wav()` (in the vendored `dysarthria_analysis.py`) uses `ffmpeg` to
  normalize non-standard WAV encodings before Praat reads them. It already degrades
  gracefully without `ffmpeg`: it prints a warning and returns the original file path
  unchanged, so the pipeline does not hard-fail if `ffmpeg` is missing.
- This is a low-stakes engineering call (not product/legal), so it can be decided and
  executed directly by whoever implements Phase 2, unlike tasks 1.1 and 1.3.
- `openspec/design/sustained-phonation-v1-uc4.md` already documents a lean-toward-yes
  recommendation: it's a one-line Dockerfile change and removes a silent-degradation
  failure mode.

STEPS
1. Locate the worker's Dockerfile (or shared base image) in the repo.
2. Note the current image size as a baseline (`docker images` or equivalent).
3. If proceeding now: add `ffmpeg` via `apt-get install -y --no-install-recommends
   ffmpeg` (and `apt-get clean` / remove apt lists afterward to control image bloat).
4. Rebuild the worker image and confirm:
   a. the build succeeds,
   b. `ffmpeg -version` runs successfully inside the container,
   c. record the before/after image size delta.
5. If deferring to D10 instead: record that decision and the rationale (e.g. timeline
   pressure, wanting to bundle it with D10's broader recording-validation work) in
   this tasks.md file, and add it explicitly to D10's task list so it isn't lost.

OUTPUT
A short note: which option was chosen, and either the image size delta (if added now)
or the explicit carry-forward note to D10 (if deferred).
```

## Phase 2: Vendor the Analysis Script

- [x] 2.1 Add `api/app/analysis/vendor/dysarthria_analysis.py` as an unmodified copy of the upload.
- [x] 2.2 Add `praat-parselmouth` to backend dependencies.
- [ ] 2.3 Add `ffmpeg` to the worker Dockerfile (per 1.4's timing decision).
- [ ] 2.4 **Empirically determine** whether `analyze_sustained_vowel` raises `parselmouth.PraatError` or returns NaN/zero values on a silence-only WAV — this gates task 3.3's exact guard implementation. Run it locally against a quick synthetic silence fixture before writing adapter code.

## Phase 3: Adapter Implementation

- [ ] 3.1 Create `api/app/analysis/errors.py` (or extend the D8 module) with `InsufficientSignalError`.
- [ ] 3.2 Create `api/app/analysis/functions/voice.py`: `sustained_phonation(wav_path, params) -> dict`, decorated `@register_analysis("sustained_phonation_v1")`, `FUNCTION_VERSION = "v1"`.
- [ ] 3.3 Implement the guard (Praat-error catch + zero/NaN check) per task 2.4's finding.
- [ ] 3.4 Wire `params.get("f0min", 75)` / `params.get("f0max", 400)` through to `analyze_sustained_vowel`.
- [ ] 3.5 Wire the module into `api/app/analysis/functions/__init__.py`.

## Phase 3 – Prompt 3.1
```text
OBJECTIVE
Implement the FTM adapter that invokes the vendored sustained phonation analyzer
and converts its output into the canonical registry result format.

CONTEXT
- The vendored implementation must remain unchanged.
- The adapter is responsible for translating between FTM models and the vendored API.
- The worker will invoke the adapter via the analysis registry.

STEPS
1. Create the sustained phonation adapter.
2. Accept the FTM analysis request model.
3. Invoke the vendored implementation.
4. Convert the returned metrics into the registry output model.
5. Do not embed business logic or scoring.
6. Keep the adapter deterministic.

OUTPUT
Record:
- files created
- registry interface implemented
- metrics successfully mapped
```

## Phase 3 – Prompt 3.2
```text
OBJECTIVE
Register the sustained_phonation_v1 analyzer in the analysis registry.

CONTEXT
The registry resolves analysis_setup.metric_api_endpoint to an executable analysis implementation.

STEPS
1. Locate the registry.
2. Register sustained_phonation_v1.
3. Verify duplicate registrations are rejected.
4. Verify registry lookup succeeds.

OUTPUT
Record:
- registry entry added
- lookup succeeds
- duplicate protection verified
```

## Phase 3 – Prompt 3.3
```text
OBJECTIVE
Normalize all exceptions produced by the vendored analyzer into FTM analysis errors.

CONTEXT
Worker code should never depend on implementation-specific exceptions.

STEPS
1. Identify analyzer exceptions.
2. Translate them into FTM exceptions.
3. Preserve original cause.
4. Log diagnostics.
5. Return deterministic error codes.

OUTPUT
Record:
- exception mapping
- handled failure cases
```

## Phase 3 – Prompt 3.4
```text
OBJECTIVE
Construct the registry payload expected by the UC6 worker.

STEPS
1. Build metrics dictionary.
2. Preserve metric keys.
3. Return metadata.
4. Validate schema compatibility.

OUTPUT
Compatibility report.
```

## Phase 3 – Prompt 3.5
```text
OBJECTIVE
Verify end-to-end integration between UC4 and the UC6 registry worker.

STEPS
1. Execute analysis.
2. Verify registry resolution.
3. Verify adapter execution.
4. Verify persistence.
5. Verify completion.

OUTPUT
Execution summary.
```



## Phase 4: Data — `metric_definition` Seed

- [ ] 4.1 Confirm/finalize real column names against the live schema (carried over from the original D9 scope).
- [ ] 4.2 Add 5 seed rows (`phonation_duration_sec`, `jitter_local_pct`, `shimmer_local_pct`, `hnr_db`, `volume_std_db`), weights per task 1.3's decision (flat 0.2 each as the documented default if no domain split is adopted).

## Phase 4 – Prompt 4.1
```text
OBJECTIVE
Populate metric_definition with the sustained phonation metrics.

STEPS
1. Seed five metric_definition rows.
2. Preserve metric keys.
3. Use approved engineering default weights.
4. Do not introduce domain/group columns.

OUTPUT
Inserted rows summary.
```

## Phase 4 – Prompt 4.2
```text
OBJECTIVE
Verify analysis_setup references sustained_phonation_v1 through metric_api_endpoint.

STEPS
1. Locate seed.
2. Verify exercise #1.
3. Confirm metric_api_endpoint = sustained_phonation_v1.

OUTPUT
Verification report.
```

## Phase 4 – Prompt 4.3
```text
OBJECTIVE
Verify SQL-first consistency.

STEPS
1. Compare ftm_schema.sql.
2. Compare ORM models.
3. Compare migrations.
4. Record discrepancies.

OUTPUT
Consistency report.
```

## Phase 4 – Prompt 4.4
```text
OBJECTIVE
Verify migration idempotency.

STEPS
1. Create empty DB.
2. Run migrations.
3. Repeat.
4. Verify success.

OUTPUT
Migration validation.
```


## Phase 5: Testing

- [ ] 5.1 Add WAV fixtures: clear sustained vowel (~12s), short/borderline (~2s), silence-only, noisy background.
- [ ] 5.2 Unit test: clear fixture returns five finite, plausible-range values.
- [ ] 5.3 Unit test: silence fixture raises `InsufficientSignalError` (asserting the specific failure mode found in task 2.4).
- [ ] 5.4 Unit test: short/borderline fixture — assert the same guard fires or document why not.
- [ ] 5.5 Unit test: noisy fixture returns a result without raising, with worse values than the clean fixture.
- [ ] 5.6 Unit test: determinism — same fixture processed twice yields identical output.
- [ ] 5.7 Unit test: `ffmpeg`-unavailable fallback still completes on a standard WAV (mock `shutil.which`).
- [ ] 5.8 Extend `api/tests/test_worker.py` with one real job against `sustained_phonation_v1`, asserting 5 `recording_metric` rows under the correct `pseudonym_id`.
- [ ] 5.9 Data assertion test: `metric_definition` rows for `sustained_phonation_v1` exist and weights sum to `1.0`.
- [ ] 5.10 Run `PYTHONPATH=api pytest api/tests -q` locally.
- [ ] 5.11 Confirm worker image build time/size is still acceptable after adding `parselmouth` (bundles a compiled Praat binary).

## Phase 5 – Prompt 5.1
```text
OBJECTIVE
Create unit tests for the sustained phonation adapter.

STEPS
1. Mock analyzer.
2. Verify metric mapping.
3. Verify metadata.
4. Verify failures.

OUTPUT
Test summary.
```

## Phase 5 – Prompt 5.2
```text
OBJECTIVE
Create registry tests.

STEPS
1. Verify registration.
2. Verify lookup.
3. Verify duplicate detection.
4. Verify unknown endpoint handling.

OUTPUT
Registry test report.
```

## Phase 5 – Prompt 5.3
```text
OBJECTIVE
Validate analysis using a valid sustained phonation recording.

STEPS
1. Execute analyzer.
2. Verify five metrics.
3. Verify output schema.

OUTPUT
Execution summary.
```

## Phase 5 – Prompt 5.4
```text
OBJECTIVE
Validate analyzer behaviour for silent or invalid recordings.

STEPS
1. Execute silent recording.
2. Record behaviour.
3. Verify deterministic failure.

OUTPUT
Failure characterization.
```

## Phase 5 – Prompt 5.5
```text
OBJECTIVE
Create an end-to-end integration test exercising the UC6 worker.

STEPS
1. Submit analysis job.
2. Execute worker.
3. Verify persistence.
4. Verify completion.

OUTPUT
Integration summary.
```

## Phase 5 – Prompt 5.6
```text
OBJECTIVE
Review overall test coverage.

STEPS
1. Execute full suite.
2. Review coverage.
3. Identify gaps.

OUTPUT
Coverage summary.
```


## Phase 6: Wrap-up

- [ ] 6.1 Confirm this closes the FTM plan D9 milestone: *"paciente graba ej.1, WAV seguro, métricas extraídas por función"*, now with real clinical metrics instead of the original sketch.
- [ ] 6.2 Note in the D13 backlog item (`ddk_rate_v1`) that `analyze_ddk`/`analyze_pataka` are already vendored and ready to wrap with the same adapter pattern.

## Phase 6 – Prompt 6.1
```text
OBJECTIVE
Update architecture documentation after implementation.

STEPS
1. Review ADRs.
2. Review Explore.
3. Review Design.
4. Update references.

OUTPUT
Documentation changes.
```

## Phase 6 – Prompt 6.2
```text
OBJECTIVE
Verify implementation documentation matches the repository.

STEPS
1. Compare docs with code.
2. Correct stale references.
3. Verify terminology consistency.

OUTPUT
Verification report.
```

## Phase 6 – Prompt 6.3
```text
OBJECTIVE
Review all open questions raised during UC4.

STEPS
1. Identify unresolved items.
2. Mark resolved items.
3. Record remaining decisions.

OUTPUT
Updated Open Questions.
```

## Phase 6 – Prompt 6.4
```text
OBJECTIVE
Execute the UC4 acceptance checklist.

STEPS
1. Verify implementation.
2. Verify tests.
3. Verify documentation.
4. Verify registry integration.
5. Verify worker execution.

OUTPUT
Acceptance report.
```

## Phase 6 – Prompt 6.5
```text
OBJECTIVE
Prepare the implementation for merge.

STEPS
1. Review modified files.
2. Remove temporary code.
3. Verify formatting.
4. Verify tests.
5. Produce implementation summary.

OUTPUT
Ready-for-merge report.
```
