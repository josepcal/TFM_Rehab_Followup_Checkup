# Tasks: Sustained Phonation Analysis Function (`sustained_phonation_v1`, UC-04)

> **Revised:** wraps the vendored `analyze_sustained_vowel` instead of writing librosa
> logic from scratch.
>
> **Re-aligned (this revision):** every prompt below now maps 1:1 to exactly one
> checklist task, in both directions — no checklist item without a prompt, no prompt
> without a checklist item. Specifically:
> - Phase 1/2 progress (checkmarks, the task 2.4 finding) from the parallel work is
>   preserved and integrated, not discarded.
> - Phase 3's guard prompts (3.3) now reflect task 2.4's actual empirical finding
>   (silence does not raise `parselmouth.PraatError`; a new `MIN_VOICED_SECONDS` floor
>   is needed) instead of the original, disproven assumption. `design.md` and
>   `specs.md` were patched to match — see the small revision notes at the top of each.
> - Two prompts generated under "Phase 4" that didn't correspond to either of Phase 4's
>   two checklist tasks (SQL-first consistency, migration idempotency) were moved to
>   Phase 5 as new tasks 5.12/5.13, since that's where whole-slice QA checks belong.
> - Phase 5 had 11 checklist tasks but only 6 prompts; Phase 6 had 2 checklist tasks
>   but 5 prompts. Both are rebuilt below with one prompt per task (Phase 5 now has 13
>   tasks counting 5.12/5.13; Phase 6 now has 6, absorbing the extra wrap-up prompts
>   that were generated without checklist entries — acceptance check and merge prep are
>   genuinely useful, just needed a home).
> - Task 5.1's fixture list is corrected: the checklist previously called for a
>   "short/borderline (~2s)" fixture, but design.md's own test table (and the
>   `MIN_VOICED_SECONDS=1.0` floor introduced by the 2.4 finding) needs a fixture
>   *below* the floor (~0.3s) to actually exercise the guard — ~2s would just be a
>   valid recording.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 250-400 (incl. ~620-line vendored file counted as a single low-risk addition) |
| 400-line budget risk | Medium — mainly from vendoring the whole script in one PR |
| Chained PRs recommended | Optional |
| Suggested split | PR #1: vendor file + adapter + deps/Dockerfile → PR #2: metric_definition seed + tests |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain (only if PR #1 alone exceeds the 400-line budget after counting the vendored file) |
| Current status | Phase 1 (minus 1.4) and Phase 2.1/2.2/2.4 reported done; Phase 2.3, Phase 3 onward not yet started. |

Decision needed before apply: Yes — task 1.4 is still open (see flag below); confirm before relying on Phase 2 Prompt 2.3 as settled.

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Vendor `dysarthria_analysis.py` + add dependencies | PR 1 | Reported done (2.1, 2.2). |
| 2 | Adapter (`voice.py`) + error type | PR 1 | Not started — Phase 3. |
| 3 | `metric_definition` seed (5 rows) | PR 2 | Not started — Phase 4. |
| 4 | Fixtures + tests, including the degenerate-input failure-mode probe | PR 2 | The probe itself (2.4) is done — see Finding below. Fixtures/tests (Phase 5) not started. |

## Phase 1: Confirm Open Questions Before Implementation

- [x] 1.1 Confirm vendoring the full `dysarthria_analysis.py` is acceptable (ownership/license, given it was supplied directly rather than pulled from a package registry). ⚠ *Checked, but Prompt 1.1's required OUTPUT (who owns it, the attribution header text) isn't recorded anywhere in this file. Backfill that note before treating Phase 2's vendoring as fully auditable.*
- [x] 1.2 Confirm exercise #1's `analysis_setup` row points at `"sustained_phonation_v1"` (per FTM plan §12 step 6; carried over from the original D9 scope, unaffected by this revision). ⚠ *Same gap — no recorded column name or seed-row confirmation in this file. Backfill per Prompt 1.2's OUTPUT.*
- [x] 1.3 Decide whether `metric_definition` needs a `domain` field to separate `phonation_duration_sec` (respiratory_support) from the other four metrics (voice_stability) — get product/clinical input; if deferred, document the flat-weight model as a known simplification. ⚠ *Same gap — assuming option (b) (flat model) was applied as the documented default per Prompt 1.3 step 3, since no domain column appears anywhere else in this revision. Confirm explicitly.*
- [ ] 1.4 Decide timing for adding `ffmpeg` to the worker image: this slice (D9) or D10's hardening pass. ⚠ **Inconsistency found:** this task is still unchecked, but Phase 2's generated Prompt 2.3 (now rewritten below) presupposed *"Decision D9 approved adding `ffmpeg` now"* without that decision being recorded here. Resolve 1.4 explicitly — check the box with the chosen option — before running Phase 2's Prompt 2.3, rather than letting a downstream prompt's assumption stand in for a recorded decision.

### Phase 1 — Execution Prompts

Unchanged from the prior revision — already aligned 1:1 with the four tasks above and not affected by the task 2.4 finding.

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
- A downstream prompt (Phase 2, Prompt 2.3) already assumes this was decided "add
  now" — if that's correct, this task's checkbox should be the place that decision is
  actually recorded, not an unstated assumption in a later prompt.

STEPS
1. Locate the worker's Dockerfile (or shared base image) in the repo.
2. Note the current image size as a baseline (`docker images` or equivalent).
3. If proceeding now: record that decision here explicitly, then follow Phase 2's
   Prompt 2.3 to execute it.
4. If deferring to D10 instead: record that decision and the rationale (e.g. timeline
   pressure, wanting to bundle it with D10's broader recording-validation work) in
   this tasks.md file, and add it explicitly to D10's task list so it isn't lost —
   then Phase 2's Prompt 2.3 should be skipped, not executed.

OUTPUT
A recorded decision ("add now" or "defer to D10") with rationale, checked off above.
This unblocks Phase 2, Prompt 2.3.
```

## Phase 2: Vendor the Analysis Script

- [x] 2.1 Add `api/app/analysis/vendor/dysarthria_analysis.py` as an unmodified copy of the upload.
- [x] 2.2 Add `praat-parselmouth` to backend dependencies.
- [ ] 2.3 Add `ffmpeg` to the worker Dockerfile. **Gated on task 1.4** — do not run until 1.4 is explicitly checked off above.
- [x] 2.4 **Empirically determine** whether `analyze_sustained_vowel` raises `parselmouth.PraatError` or returns NaN/zero values on a silence-only WAV — this gated task 3.3's guard implementation. **Done — see Finding below.**

### Finding — Task 2.4: Degenerate Signal Characterization

A characterization run executed the vendored `analyze_sustained_vowel` against three synthetic PCM WAV fixtures: silence, a very short voiced sine-wave sample, and a very low-amplitude voiced sine-wave sample.

- **Silence:** did *not* raise an exception. Returned `phonation_duration_sec=0.0`, NaN for `jitter_local_pct`/`shimmer_local_pct`/`hnr_db`, and `volume_std_db=0.0`. Empty stdout/stderr.
- **Short voiced sample:** returned a metric dict without exception — no NaNs reported.
- **Low-amplitude voiced sample:** also returned a metric dict without exception.

**Implication for Phase 3 (already applied to `design.md`'s guard code and `specs.md`'s requirements):** the adapter cannot rely on a caught exception, nor on duration alone, to detect degenerate input. The guard needs two independent checks: (1) any NaN-valued metric (catches the pure-silence case), and (2) `phonation_duration_sec` below an explicit `MIN_VOICED_SECONDS` floor — default `1.0`, configurable via `params.min_duration_sec`, flagged as an engineering placeholder pending clinical input — since a short/quiet *voiced* sample passes the NaN check but is still not a clinically valid attempt. `parselmouth.PraatError` is kept as a defensive catch for malformed/corrupt files, not as the primary degenerate-input path — that assumption was disproven by this finding.

### Phase 2 — Execution Prompts

#### Prompt 2.1 — Vendor the file verbatim *(reference — already executed)*

```
OBJECTIVE
Vendor the approved `dysarthria_analysis.py` implementation into the analysis
package without changing its behaviour.

CONTEXT
- Task 1.1 must be resolved (license/attribution) before this runs — see the ⚠ flag
  on task 1.1 above if that wasn't actually recorded.
- The vendored module must remain an immutable upstream snapshot; all FTM-specific
  integration belongs in the adapter implemented during Phase 3.
- Do not change algorithm logic, thresholds, function signatures, or outputs.

STEPS
1. Create `api/app/analysis/vendor/dysarthria_analysis.py`.
2. Copy the implementation verbatim.
3. Add the attribution/licensing header agreed in task 1.1.
4. If necessary, adjust only import paths required for the local package layout —
   do not modify algorithm behaviour.
5. Create `api/app/analysis/vendor/__init__.py` if the package doesn't already exist.
6. Verify the module imports successfully and `analyze_sustained_vowel` is importable.
7. Record any unavoidable deviations from the upstream file (expected: none, or
   import-path adjustments only).

OUTPUT
Files created, confirmation of behavioral identity with the source, confirmation
attribution is present, import verification result, list of deviations (if any).
```

#### Prompt 2.2 — Add `praat-parselmouth` dependency *(reference — already executed)*

```
OBJECTIVE
Add the `praat-parselmouth` PyPI package so `import parselmouth` resolves in both
the API and worker environments.

CONTEXT
- New dependency beyond the FTM plan's original stack (librosa, scipy, soundfile,
  numpy) — required by the vendored module.
- Ships a compiled Praat binary inside the wheel; a larger/slower install than a
  pure-Python package is expected, not a sign of a broken install.

STEPS
1. Identify the dependency manifest and its existing version-pinning convention.
2. Add `praat-parselmouth`, pinned, following that same convention.
3. Install into the dev environment; confirm `python -c "import parselmouth"`.
4. Regenerate any lockfile per the project's normal process.
5. Note install size/time if surprisingly large (feeds into task 5.11).

OUTPUT
Updated manifest (+ lockfile if applicable), confirmed working import, installed
version recorded.
```

#### Prompt 2.3 — Add `ffmpeg` to the worker image *(conditional — gated on task 1.4)*

```
OBJECTIVE
Execute the `ffmpeg` decision recorded in task 1.4 — and only that decision, not an
assumption about what it should be.

CONTEXT
- This prompt does nothing on its own authority. Check task 1.4's checkbox and
  recorded rationale in this tasks.md file before proceeding.
- This only applies to the **worker** image, not the API image.

STEPS
1. Read task 1.4's recorded decision.
2. If "add now":
   a. Locate the worker's Dockerfile.
   b. Add: `RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*`
   c. Rebuild the worker image; confirm `ffmpeg -version` runs inside a container.
   d. Record the before/after image size delta (cross-link with task 1.4's note).
   e. Check off task 2.3 above.
3. If "defer to D10": do not modify the Dockerfile. Confirm D10's task list already
   carries this item (per task 1.4's instruction); check off task 2.3 above as
   "deferred, see D10" rather than leaving it silently unchecked with no explanation.
4. If task 1.4 is still unchecked: stop. Do not guess. Go resolve 1.4 first.

OUTPUT
Either a working worker image with `ffmpeg` verified, or an explicit "deferred to
D10" note — never a silent no-op, and never a decision made by this prompt itself.
```

#### Prompt 2.4 — Determine the degenerate-input failure mode *(reference — already executed, see Finding above)*

```
OBJECTIVE
Empirically determine what `analyze_sustained_vowel` actually does on degenerate
input (silence, very short voiced, very low-amplitude voiced), to ground Phase 3's
guard logic in observed behavior instead of assumption.

STATUS: COMPLETE. See "Finding — Task 2.4" above for the result and its
implications for Phase 3. This prompt is retained for reproducibility, not as an
open to-do.

ORIGINAL STEPS (for reference / re-running if the vendored file changes upstream)
1. Generate synthetic PCM WAV fixtures: digital silence, low-amplitude noise floor,
   short voiced tone.
2. Run `analyze_sustained_vowel` against each; capture return value, exception (if
   any), and stdout/stderr.
3. Compare against the guard logic assumed in `design.md` at the time; update it if
   the assumption was wrong (it was — see Finding above).

OUTPUT
Already delivered: see "Finding — Task 2.4" above, and the resulting patch to
`design.md`'s guard code and `specs.md`'s requirements.
```

## Phase 3: Adapter Implementation

- [ ] 3.1 Create `api/app/analysis/errors.py` (or extend the D8 module) with `InsufficientSignalError`.
- [ ] 3.2 Create `api/app/analysis/functions/voice.py`: `sustained_phonation(wav_path, params) -> dict`, decorated `@register_analysis("sustained_phonation_v1")`, `FUNCTION_VERSION = "v1"` — happy-path call to `analyze_sustained_vowel` with hardcoded defaults, no guard yet (that's 3.3) and no `params`-driven thresholds yet (that's 3.4).
- [ ] 3.3 Extend 3.2 with the degenerate-input guard: NaN check + `MIN_VOICED_SECONDS` floor, per task 2.4's finding (not the original `PraatError`-only assumption).
- [ ] 3.4 Replace the hardcoded `f0min`/`f0max` (and add `min_duration_sec`) with `params.get(...)` reads.
- [ ] 3.5 Wire the module into `api/app/analysis/functions/__init__.py` so the decorator runs at process start.

### Phase 3 — Execution Prompts

#### Prompt 3.1 — `InsufficientSignalError`

```
OBJECTIVE
Add the `InsufficientSignalError` exception type the adapter will raise for
degenerate/unusable input.

CONTEXT
- D8 already has an analysis error module (referenced by `analysis-registry-worker-uc6`'s
  design doc), at minimum containing `UnknownAnalysisFunction`. Locate and extend it —
  do not assume a brand-new file is required.  for
  this type in the worker — it must be handled by the same generic path as every other
  function failure.
- This single exception type covers two distinct situations (NaN result, and
  below-`MIN_VOICED_SECONDS` duration per task 2.4's finding) — the distinction lives
  in the message text (task 3.3), not in separate exception subclasses, unless a
  reviewer specifically wants that granularity.

STEPS
1. Locate `api/app/analysis/errors.py` (or equivalent).
2. Add `class InsufficientSignalError(Exception): pass`.
3. Confirm (by reading the worker code, not assuming) that a generic exception handler
   already wraps registered-function execution and needs no changes for this new type.

OUTPUT
File path used; confirmation that the worker's existing generic handler covers
`InsufficientSignalError` without modification.
```

#### Prompt 3.2 — Adapter skeleton (happy path only)

```
OBJECTIVE
Create the registered `sustained_phonation_v1` function as a thin adapter calling
the vendored `analyze_sustained_vowel`, happy path only — no guard (3.3), no
`params`-driven thresholds (3.4) yet. Keep this step reviewable on its own.

CONTEXT
- File: `api/app/analysis/functions/voice.py` (new).
- Registration is automatic via the `@register_analysis("sustained_phonation_v1")`
  decorator at import time — there is no separate manual "register in the registry"
  step. The function isn't live until 3.5 wires the import into `__init__.py`.
- Import `analyze_sustained_vowel` and `ensure_pcm_wav` from
  `app.analysis.vendor.dysarthria_analysis` (built in 2.1).

STEPS
1. Create `api/app/analysis/functions/voice.py`.
2. Add `FUNCTION_VERSION = "v1"` at module level.
3. Define:
   @register_analysis("sustained_phonation_v1")
   def sustained_phonation(wav_path: str, params: dict) -> dict:
       normalized_path = ensure_pcm_wav(wav_path)
       result = analyze_sustained_vowel(normalized_path, f0min=75, f0max=400)
       return result
4. Do not add error handling or guards yet — that's 3.3.
5. Confirm the module imports cleanly and the function runs against a known-good
   fixture (manual smoke test is fine here; formal tests are Phase 5).

OUTPUT
File created; confirmation it returns the expected 5-key dict on a clean fixture.
```

#### Prompt 3.3 — Degenerate-input guard (finding-informed)

```
OBJECTIVE
Extend the Prompt 3.2 adapter with the degenerate-input guard, using the actual
empirically observed failure modes from task 2.4 — not the originally assumed
(and disproven) `PraatError`-only behavior.

CONTEXT
- Task 2.4's finding: silence returns `phonation_duration_sec=0.0` and NaN values,
  WITHOUT raising. A short/quiet but technically-voiced sample returns cleanly with
  neither an exception nor a NaN — so duration/NaN checks alone don't catch it.
- This means the guard needs: (a) a NaN check across all returned values, and (b) an
  explicit minimum-duration floor, independent of (a).
- `parselmouth.PraatError` should still be caught, but as a defensive measure for
  malformed/corrupt audio files — a different failure mode than the ones task 2.4
  actually observed — not as the primary mechanism.
- The exact code is already specified in `design.md`'s Interfaces/Contracts section
  (patched after this finding) — copy it rather than re-deriving it independently.

STEPS
1. Add `MIN_VOICED_SECONDS = 1.0` as a module-level constant in `voice.py`, with a
   comment noting it's an engineering default pending clinical input (matches the
   Explore doc's open-question pattern for unvalidated thresholds).
2. Wrap the `analyze_sustained_vowel` call in `try/except parselmouth.PraatError`,
   re-raising as `InsufficientSignalError` (defensive path).
3. After a successful call, check: `duration < MIN_VOICED_SECONDS` OR any value in
   the result is `None`/NaN → raise `InsufficientSignalError` with a message that
   distinguishes duration-floor rejection from NaN rejection (see specs.md's two
   separate scenarios: "Silence-only recording" vs. "Technically voiced but too
   short").
4. Do not yet wire `MIN_VOICED_SECONDS` to `params` — that's 3.4.

OUTPUT
Updated `voice.py` matching `design.md`'s patched code block; confirmation (manual
or via the Phase 5 fixtures once they exist) that silence and below-floor inputs
both raise, with distinguishable messages.
```

#### Prompt 3.4 — `params`-driven thresholds

```
OBJECTIVE
Replace the hardcoded `f0min=75`, `f0max=400`, and `MIN_VOICED_SECONDS=1.0` defaults
in the Prompt 3.2/3.3 adapter with `params.get(...)` reads, per specs.md's
"Pitch range is configurable via `params`" requirement.

CONTEXT
- `params` comes from `analysis_setup.function_params` at runtime (FTM plan §5.2) —
  this function must not assume it's always empty.
- Keep the same fallback values as defaults: `f0min=75`, `f0max=400`,
  `min_duration_sec=1.0`.

STEPS
1. Replace the hardcoded call with:
     analyze_sustained_vowel(
         normalized_path,
         f0min=params.get("f0min", 75),
         f0max=params.get("f0max", 400),
     )
2. Replace the guard's duration comparison with:
     min_duration = params.get("min_duration_sec", MIN_VOICED_SECONDS)
     ... duration < min_duration ...
3. Confirm `params = {}` still produces the documented defaults (specs.md scenario
   "Default pitch range used when params is empty").
4. Confirm an explicit override (e.g. `{"f0min": 100, "f0max": 300}`) is honored.

OUTPUT
Updated `voice.py`; confirmation both the default and override scenarios from
specs.md behave as specified (formal tests land in Phase 5; a manual check is
enough here).
```

#### Prompt 3.5 — Wire into the registry import point

```
OBJECTIVE
Make `sustained_phonation_v1` actually resolvable by the D8 worker by importing
`voice.py` at process start.

CONTEXT
- The D8 registry resolves functions by name only if their module has been imported
  somewhere — the decorator runs at import time, not at call time.
- `api/app/analysis/functions/__init__.py` is the established import point per the
  D8 design doc.

STEPS
1. Add `from . import voice` (or equivalent) to
   `api/app/analysis/functions/__init__.py`.
2. Confirm that starting the worker process (or importing the `functions` package in
   a Python shell) causes `sustained_phonation_v1` to appear in the registry.
3. Confirm a job referencing `sustained_phonation_v1` no longer raises
   `UnknownAnalysisFunction` — it previously did, since nothing registered that name
   before this slice.

OUTPUT
Updated `__init__.py`; confirmation the registry resolves the name correctly.
This closes Phase 3.
```

## Phase 4: Data — `metric_definition` Seed

- [x] 4.1 Confirm/finalize real column names on `metric_definition` against the live schema (distinct from task 1.2, which covered `analysis_setup`'s column name, not `metric_definition`'s).
- [x] 4.2 Add 5 seed rows (`phonation_duration_sec`, `jitter_local_pct`, `shimmer_local_pct`, `hnr_db`, `volume_std_db`), weights per task 1.3's decision (flat 0.2 each as the documented default if no domain split is adopted).

> Two prompts previously generated under "Phase 4" — a re-verification of
> `analysis_setup`'s seed row, and broader SQL-first/migration-idempotency checks —
> didn't correspond to either task above. The `analysis_setup` re-check duplicated
> task 1.2 and was dropped. The SQL-first and migration-idempotency checks are real,
> useful QA steps but belong with the rest of the slice's testing, not specifically
> with metric seeding — they're now tasks 5.12 and 5.13.

### Phase 4 — Execution Prompts

#### Prompt 4.1 — Confirm `metric_definition` column names

```
OBJECTIVE
Confirm the real column names on `metric_definition` (this table, not
`analysis_setup` — see task 1.2 for that one) against the live schema, per ADR-0008's
description of "metric_key, label, unit, weight."

CONTEXT
- ADR-0017: `ftm_schema.sql` is the SQL-first source of truth; `models.py` is the
  hand-mirrored ORM layer.
- `design.md`'s illustrative seed SQL uses `function_name, metric_key, label, unit,
  weight` as column names — explicitly flagged there as "illustrative... not a
  verified migration."

STEPS
1. Check `ftm_schema.sql` for the actual `metric_definition` table definition.
2. Cross-check `models.py` for the matching ORM model.
3. Note any column-name discrepancy against `design.md`'s illustrative SQL and
   correct that doc if needed.
4. Confirm whether the table already exists (ADR-0008 implies the data layer is
   implemented) or whether this slice needs a migration to create it.

OUTPUT
Confirmed column names; note on whether a new migration is needed before 4.2 can
insert rows.
```

#### Prompt 4.2 — Seed the 5 `metric_definition` rows

```
OBJECTIVE
Insert the 5 `metric_definition` rows for `sustained_phonation_v1`.

CONTEXT
- Metrics: `phonation_duration_sec` (s), `jitter_local_pct` (%), `shimmer_local_pct`
  (%), `hnr_db` (dB), `volume_std_db` (dB).
- Weighting depends on task 1.3's decision: flat 0.2 each (documented MVP default) 
  unless a domain-grouped scheme was approved instead — check task 1.3's recorded
  outcome before choosing weights here.
- Use the real column names confirmed in 4.1, not the illustrative ones in
  `design.md` if they turned out to differ.

STEPS
1. Write the seed migration/script using the confirmed schema (4.1).
2. Insert all 5 rows, with weights per 1.3's outcome.
3. Confirm the 5 rows exist and (if flat-weighted) sum to 1.0.

OUTPUT
Migration/seed file; confirmation query result showing all 5 rows present with
correct weights.
```

## Phase 5: Testing

- [x] 5.1 Add WAV fixtures: clear sustained vowel (~12s), **below-floor short** (~0.3s, must be under `MIN_VOICED_SECONDS` to exercise the duration guard — corrected from the previous "~2s," which would actually be a *valid* recording, not a guard-triggering one), silence-only, noisy background. Optionally a boundary fixture (~1.2s, just above the floor) if boundary precision matters.
- [x] 5.2 Unit test: clear fixture returns five finite, plausible-range values.
- [x] 5.3 Unit test: silence fixture raises `InsufficientSignalError`, with a message attributable to the NaN/zero path (per task 2.4's finding — not a `PraatError`).
- [x] 5.4 Unit test: below-floor short fixture raises `InsufficientSignalError` via the `MIN_VOICED_SECONDS` floor specifically — assert the message distinguishes this from 5.3's NaN-path rejection.
- [x] 5.5 Unit test: noisy fixture returns a result without raising, with worse values than the clean fixture.
- [x] 5.6 Unit test: determinism — same fixture processed twice yields identical output.
- [x] 5.7 Unit test: `ffmpeg`-unavailable fallback still completes on a standard WAV (mock `shutil.which`).
- [x] 5.8 Extend `api/tests/test_worker.py` with one real job against `sustained_phonation_v1`, asserting 5 `recording_metric` rows under the correct `pseudonym_id`.
- [x] 5.9 Data assertion test: `metric_definition` rows for `sustained_phonation_v1` exist and weights sum to `1.0`.
- [x] 5.10 Run `PYTHONPATH=api pytest api/tests -q` locally.
- [ ] 5.11 Confirm worker image build time/size is still acceptable after adding `parselmouth` (bundles a compiled Praat binary).
- [ ] 5.12 **(moved from a mis-homed Phase 4 prompt)** Verify SQL-first consistency: `ftm_schema.sql` vs. ORM `models.py` vs. applied migrations agree on `analysis_setup` and `metric_definition` shape (ADR-0017).
- [ ] 5.13 **(moved from a mis-homed Phase 4 prompt)** Verify migration idempotency: apply migrations to an empty DB, then re-apply, and confirm no errors / no duplicate seed rows.

### Phase 5 — Execution Prompts

#### Prompt 5.1 — Fixtures

```
OBJECTIVE
Add the WAV fixtures Phase 5's tests depend on.

CONTEXT
Corrected fixture set (see the revision note at the top of this file for why):
clear (~12s, happy path), below-floor short (~0.3s, must trigger the
MIN_VOICED_SECONDS guard), silence (~3s, must trigger the NaN-path guard), noisy
background (must NOT raise). A ~1.2s boundary fixture is optional.

STEPS
1. Record or synthesize each fixture; check in under `api/tests/fixtures/audio/`.
2. Name them descriptively: e.g. `clear_vowel_12s.wav`, `below_floor_03s.wav`,
   `silence_3s.wav`, `noisy_background.wav`.
3. Confirm each is mono 16-bit PCM (or confirm `ensure_pcm_wav` normalizes it
   correctly if not).

OUTPUT
Fixture files checked in; one-line description of each in the test file's docstring
or a fixtures README.
```

#### Prompt 5.2 — Happy-path unit test

```
OBJECTIVE
Test 5.2: clear fixture returns five finite, plausible-range values.

STEPS
1. Call `sustained_phonation(CLEAR_FIXTURE_PATH, {})`.
2. Assert all 5 keys present, all values finite (`not math.isnan`).
3. Range-assert loosely (e.g. `phonation_duration_sec` roughly matches the
   fixture's known voiced duration) — avoid exact-float assertions, since audio
   decoding isn't bit-identical across environments.

OUTPUT
Passing test in `api/tests/test_sustained_phonation.py`.
```

#### Prompt 5.3 — Silence raises via NaN path

```
OBJECTIVE
Test 5.3: silence fixture raises `InsufficientSignalError`, attributable to the
NaN/zero-duration path specifically (per task 2.4's finding).

STEPS
1. Call `sustained_phonation(SILENCE_FIXTURE_PATH, {})`.
2. Assert `InsufficientSignalError` is raised.
3. Assert the exception message references the NaN/zero-duration condition, not the
   duration-floor condition — this is what distinguishes this test from 5.4.

OUTPUT
Passing test confirming the silence path specifically.
```

#### Prompt 5.4 — Below-floor short input raises via duration guard

```
OBJECTIVE
Test 5.4: a short-but-technically-voiced fixture raises `InsufficientSignalError`
via the `MIN_VOICED_SECONDS` floor — the case task 2.4 found duration/NaN checks
alone would miss.

STEPS
1. Call `sustained_phonation(BELOW_FLOOR_FIXTURE_PATH, {})`.
2. Assert `InsufficientSignalError` is raised.
3. Assert the message references the minimum-duration condition, not NaN — confirms
   the right guard branch fired (distinct from 5.3).
4. If a boundary fixture (~1.2s) was added in 5.1, add a companion assertion that it
   does NOT raise.

OUTPUT
Passing test confirming the duration-floor path specifically, distinguishable from
the silence/NaN path tested in 5.3.
```

#### Prompt 5.5 — Noisy fixture degrades but doesn't fail

```
OBJECTIVE
Test 5.5: a noisy-but-usable recording returns a result without raising, with
worse (not better) voice-quality values than the clean fixture.

STEPS
1. Call `sustained_phonation` on both the clean and noisy fixtures.
2. Assert neither raises.
3. Assert the noisy fixture's `jitter_local_pct`/`shimmer_local_pct` are higher and
   `hnr_db` is lower than the clean fixture's (per specs.md's "Noisy but usable
   recording" scenario).

OUTPUT
Passing comparative test.
```

#### Prompt 5.6 — Determinism

```
OBJECTIVE
Test 5.6: identical input produces identical output across repeated runs.

STEPS
1. Run `sustained_phonation` twice on the same fixture and `params`.
2. Assert both results are exactly equal (dict equality).

OUTPUT
Passing determinism test.
```

#### Prompt 5.7 — `ffmpeg`-unavailable fallback

```
OBJECTIVE
Test 5.7: the adapter still completes on a standard WAV when `ffmpeg` is
unavailable, per `ensure_pcm_wav`'s documented graceful-degradation behavior.

STEPS
1. Mock `shutil.which` (or whatever `ensure_pcm_wav` uses internally to detect
   `ffmpeg`) to return `None`.
2. Call `sustained_phonation` on the clean fixture (already standard PCM, so no
   re-encoding should be needed regardless).
3. Assert it still returns a valid result.

OUTPUT
Passing fallback test.
```

#### Prompt 5.8 — Worker integration test

```
OBJECTIVE
Test 5.8: a real (non-fake) job against `sustained_phonation_v1`, run through the
D8 worker, produces correct persisted state.

CONTEXT
This extends `api/tests/test_worker.py` (built in D8) with the first real-function
case — D8's own tests used a fake/stub function.

STEPS
1. Enqueue a job `{recording_id, function_name: "sustained_phonation_v1"}`
   referencing the clean fixture.
2. Run the worker (or its job-processing function directly).
3. Assert `metric_result.status == "success"`.
4. Assert 5 `recording_metric` rows exist, under the correct `pseudonym_id`
   (resolved via the worker's existing pseudonym-resolution logic from D8 — not
   re-implemented here).

OUTPUT
Passing integration test in `test_worker.py`.
```

#### Prompt 5.9 — `metric_definition` data assertion

```
OBJECTIVE
Test 5.9: confirm the 5 seeded `metric_definition` rows from Phase 4 are present and
correctly weighted.

STEPS
1. Query `metric_definition` filtered by `function_name = "sustained_phonation_v1"`.
2. Assert exactly 5 rows.
3. Assert the metric_key set matches exactly: `phonation_duration_sec`,
   `jitter_local_pct`, `shimmer_local_pct`, `hnr_db`, `volume_std_db`.
4. Assert weights sum to `1.0` (within floating-point tolerance).

OUTPUT
Passing data assertion test.
```

#### Prompt 5.10 — Full local test run

```
OBJECTIVE
Confirm the whole slice passes together, not just in isolation.

STEPS
1. Run `PYTHONPATH=api pytest api/tests -q`.
2. Investigate and fix any failures before considering Phase 5 complete.

OUTPUT
Clean local test run output (paste or summarize pass/fail counts).
```

#### Prompt 5.11 — Worker image size/time check

```
OBJECTIVE
Confirm the worker image still builds in acceptable time/size after adding
`praat-parselmouth` (which bundles a compiled Praat binary) and, if 1.4 chose "add
now," `ffmpeg`.

STEPS
1. Build the worker image from a clean cache.
2. Record build time and final image size.
3. Compare against the pre-this-slice baseline (if available) or simply flag if the
   absolute numbers look concerning for the 20-day deploy cadence (ADR-0018).

OUTPUT
Build time/size numbers, with a go/flag note for the team.
```

#### Prompt 5.12 — SQL-first consistency check

```
OBJECTIVE
Verify `ftm_schema.sql`, the SQLAlchemy `models.py`, and applied migrations agree on
the shape of `analysis_setup` and `metric_definition` after this slice's changes.

CONTEXT
ADR-0017 establishes `ftm_schema.sql` as the SQL-first source of truth, with
`models.py` mirrored by hand and migrations as the living source of truth going
forward. Drift between these three is a known risk class this ADR exists to manage.

STEPS
1. Diff `ftm_schema.sql`'s table definitions for `analysis_setup`/`metric_definition`
   against the corresponding SQLAlchemy models.
2. Diff against what the applied migrations actually created in a real/test database.
3. Record any discrepancy found — do not silently "fix" one to match another without
   understanding which one is actually correct.

OUTPUT
Consistency report: either "all three agree" or an explicit list of discrepancies
with a recommended source of truth for each.
```

#### Prompt 5.13 — Migration idempotency check

```
OBJECTIVE
Confirm this slice's migrations (Phase 4's `metric_definition` seed, and any schema
migration from 4.1 if one was needed) are idempotent.

STEPS
1. Create a fresh/empty test database.
2. Run migrations to head.
3. Run migrations to head again (no-op expected).
4. Assert: no errors, and no duplicate `metric_definition` rows (this matters
   specifically because 4.2 inserts seed data, which is a common source of
   non-idempotent migrations if not guarded with an upsert/conflict clause).

OUTPUT
Pass/fail result; if duplicates appear on re-run, flag the seed migration for a fix
(`ON CONFLICT DO NOTHING`/`DO UPDATE` or an existence check) rather than leaving it.
```

## Phase 6: Wrap-up

- [ ] 6.1 Confirm this closes the FTM plan D9 milestone: *"paciente graba ej.1, WAV seguro, métricas extraídas por función"*, now with real clinical metrics instead of the original sketch.
- [ ] 6.2 Note in the D13 backlog item (`ddk_rate_v1`) that `analyze_ddk`/`analyze_pataka` are already vendored and ready to wrap with the same adapter pattern.
- [ ] 6.3 **(absorbed from a previously unhomed prompt)** Verify documentation matches the repository: compare `explore.md`/`design.md`/`specs.md` against the actual code, correct stale references, confirm terminology consistency (e.g. the `metric_api_endpoint`/`function_name` question from 1.2, if it surfaced a real discrepancy).
- [ ] 6.4 **(absorbed)** Review all open questions raised across `explore.md` and this file; mark resolved ones with their resolution, and carry forward genuinely unresolved ones rather than letting them silently disappear.
- [ ] 6.5 **(absorbed)** Run an acceptance checklist: implementation complete, tests passing, docs consistent (6.3), registry integration confirmed (3.5), worker execution confirmed (5.8).
- [ ] 6.6 **(absorbed)** Prepare for merge: review the full diff, remove any temporary/debug code, confirm formatting/linting, confirm the full test suite (5.10) passes, write a short implementation summary for the PR description.

### Phase 6 — Execution Prompts

#### Prompt 6.1 — Confirm the D9 milestone

```
OBJECTIVE
Confirm this slice closes the FTM plan's D9 milestone.

STEPS
1. Re-read the FTM plan's D9 entry: *"paciente graba ej.1, WAV seguro, métricas
   extraídas por función."*
2. Confirm: a patient can record exercise #1, the recording is stored per ADR-0006
   (signed URLs, private bucket), and metrics are now extracted via a real function
   (this slice) rather than the original librosa sketch.
3. Note explicitly that this exceeds the original D9 scope clinically (5 validated
   acoustic measures vs. 2 simplified ones) at the cost of new dependencies
   (parselmouth, optionally ffmpeg) not in the original plan.

OUTPUT
A short confirmation note for the FTM plan tracking, plus the noted scope delta.
```

#### Prompt 6.2 — D13 backlog note

```
OBJECTIVE
Make sure D13 (`ddk_rate_v1`) starts from a documented head start instead of
rediscovering that `analyze_ddk`/`analyze_pataka` are already vendored.

STEPS
1. Add a note to the D13 backlog item: the vendored
   `api/app/analysis/vendor/dysarthria_analysis.py` already contains
   `analyze_ddk`/`analyze_pataka`; D13 only needs an adapter following this slice's
   pattern (errors → skeleton → guard → params → registry wiring), not a new vendor
   step.
2. Link this slice's tasks.md as a reference implementation for that adapter pattern.

OUTPUT
Updated D13 backlog note with the link.
```

#### Prompt 6.3 — Documentation consistency

```
OBJECTIVE
Confirm `explore.md`, `design.md`, and `specs.md` for this slice match the actual
shipped code — not just each other.

STEPS
1. Re-read all three docs against the final `voice.py`, `errors.py`, and the
   `metric_definition` seed.
2. Specifically check: does `analysis_setup`'s real column name (resolved in 1.2)
   match what both docs say? Does `MIN_VOICED_SECONDS`'s default match what's
   actually in code? Do the five metric keys match exactly?
3. Correct any drift found — in the docs, not by changing working code to match
   stale docs.

OUTPUT
Either "no drift found" or a list of corrections made, with file/line references.
```

#### Prompt 6.4 — Open questions review

```
OBJECTIVE
Sweep `explore.md`'s Open Questions and this file's flagged items (the ⚠ notes on
1.1-1.3, the 1.4 gate) for resolution status.

STEPS
1. List every open question/flag across both files.
2. For each: mark resolved (with the resolution and where it's recorded) or
   explicitly carry forward as still-open, with an owner if possible.
3. Do not let an item disappear silently — every item from the sweep must end up in
   one of those two buckets.

OUTPUT
Updated Open Questions sections, plus a short summary of what's still open going
into D10+.
```

#### Prompt 6.5 — Acceptance checklist

```
OBJECTIVE
Run a final acceptance pass before this slice is considered done.

STEPS
1. Implementation: 3.1-3.5 all complete and matching `design.md`.
2. Tests: 5.1-5.13 all passing.
3. Docs: 6.3 complete, no known drift.
4. Registry integration: 3.5 confirmed (`sustained_phonation_v1` resolves, no
   `UnknownAnalysisFunction`).
5. Worker execution: 5.8 confirmed end-to-end.

OUTPUT
A pass/fail acceptance report against these five criteria, naming any that fail.
```

#### Prompt 6.6 — Merge preparation

```
OBJECTIVE
Prepare the final diff for review/merge.

STEPS
1. Review the full diff for this slice (vendor file + adapter + errors + seed +
   tests + Dockerfile if 1.4 = "add now" + doc updates).
2. Remove any temporary/debug code (e.g. print statements added during the 2.4
   characterization probe).
3. Confirm formatting/linting passes per the project's existing conventions.
4. Confirm 5.10's full test run still passes after cleanup.
5. Write a short implementation summary for the PR description: what changed, why
   (link back to the Explore doc's Decision), and the scope delta noted in 6.1.

OUTPUT
A clean, reviewable diff and a PR-ready summary.
```
