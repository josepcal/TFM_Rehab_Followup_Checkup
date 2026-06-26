# Explore: Sustained Phonation v1 (UC-04)

## User Need

UC-04 introduces the `sustained_phonation_v1` analysis function for the sustained vowel exercise. The function returns five metrics: `phonation_duration_sec`, `jitter_local_pct`, `shimmer_local_pct`, `hnr_db`, and `volume_std_db`.

## Current State

The vendored analyzer exposes `analyze_sustained_vowel` for metric extraction. Its own `score_domains()` helper is not wired into FTM, but it groups `phonation_duration_sec` as `respiratory_support` and the other four metrics as `voice_stability`.

The current MVP data model keeps `metric_definition` as a flat list of metric rows. No `domain` or equivalent grouping column is currently part of the SQL-first schema.

## Decision Brief

Decision question: should `metric_definition` gain a `domain`/grouping field now, because `sustained_phonation_v1` returns metrics that span respiratory support and voice stability? Option (a): add a `domain` column to `metric_definition`, populate it for these five rows, and use flat weight-within-domain rather than one global weight. Option (b): keep `metric_definition` flat for MVP (five metric rows, equal flat weighting where needed) and treat domain grouping as a later concern handled in the LLM insight `criteria` payload or reporting, not in the data model.

## Decision

No PO/clinical-lead answer is recorded in this task. Apply option (b) as the documented MVP default, pending PO input.

This is a known simplification, not a closed clinical/product decision. Do not introduce a `domain` column or domain-specific weighting numbers until there is explicit PO/clinical sign-off or a traceable clinical source.

## Open Questions

- Pending PO/clinical decision: should `metric_definition` add a `domain` or similar grouping field for metrics that belong to distinct clinical constructs such as `respiratory_support` and `voice_stability`?
- Pending PO/clinical decision: if domain grouping is added later, should weights be interpreted within each domain, globally across all metrics, or separately for reporting/LLM criteria?
