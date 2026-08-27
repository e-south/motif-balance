---
doc_id: motif-balance-result-inspection
title: Result inspection and catalogs
intent: Explain read-only current-result projection, trust states, and bounded review views.
audience:
  - users
  - API consumers
  - evidence producers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: reference
journey:
  - inspect
---

# Result inspection and catalogs

Inspection is a derived, read-only view over an explicit artifact contract. It
does not add files to a result, change bundle identity, accept evidence, or
discover directories recursively.

## Current results

Inspect a canonical bundle only after naming its kind:

```bash
motif-balance inspect result/ --kind bundle
motif-balance inspect result/ --kind bundle --format json
motif-balance inspect result/ --kind bundle --format html --out review.html
```

The projection reports the request, semantic versions, motif provenance,
result identities, candidate portfolio, bounded pairwise-distance state,
optimizer diagnostics, and artifact digests. Bundle inspection performs the same byte,
schema, identity, and scientific replay as `verify`. Supplying an independently
trusted `--expected-bundle-id` changes the trust basis from self-consistency to
an external identity check.

The HTML projection adds three bounded, accessible explanations over the same
verified state:

- a shared coordinate map for the top candidate's one-best-match record per motif;
- a directly labeled per-motif score profile for the returned portfolio; and
- a step plot of best-so-far scores at recorded search checkpoints.

Coordinates are zero-based and half-open. Overlapping spans show coordinate
overlap, not biological occupancy. Scores are the declared normalized motif
scores, not probabilities, and the portfolio view compares candidates only
within one run. Search progress is not a full proposal history, convergence
proof, or global-optimality claim. Exact tables remain in progressive sections
below each explanation.

When a motif view is bounded, limiting motifs are displayed before nonlimiting
motifs, and the view reports displayed and total limiting counts. Every
portfolio row also names its hard minimum and limiting motifs. Search progress
removes unchanged checkpoints only when every recorded score-change evaluation
can remain exact; otherwise it switches from a step line to explicitly labeled
sampled markers.

Execution inspection joins the verified bundle to its release and runtime
receipt. All four external anchors are required for the result to be labeled
externally verified. Without them, the complete object is checked for internal
consistency but labeled `readable_untrusted`.

Exact distance is computed only when the declared base-comparison limit permits
it. Larger valid portfolios report `not_computed_limit`, the projected work, and
the limit instead of entering an unbounded quadratic operation. The HTML review
uses progressive disclosure and bounded candidate, match, and checkpoint
tables. Every bounded visual discloses displayed and total counts; canonical
TSV and JSON remain the complete machine-readable surfaces.

## Derived catalogs

Catalogs contain bounded summaries derived from explicit, caller-named
inspections. They do not duplicate candidates, scan Storage, or scan a workspace root:

```bash
motif-balance catalog \
  --entry exact=bundle:/path/to/exact/bundle \
  --entry annealed=execution:/path/to/execution \
  --out result-catalog.json

motif-balance catalog \
  --entry exact=bundle:/path/to/exact/bundle \
  --format html --out result-catalog.html
```

`motif-balance.result-catalog/v1` is a portable review index. It is not a
canonical result bundle, a Storage manifest, a benchmark cohort, or an evidence
record. Catalog HTML is a compact compatibility index; it does not compare
quality, choose a cohort, or compute a cross-run conclusion.

## Interpretation boundary

Product inspection owns single-run integrity, request and outcome explanation,
within-portfolio distance, and optimizer diagnostics. Callers own cohorts,
model-selection rationale, rescoring policy, baselines, repeated runs,
comparisons, and claims. Artifact stores own placement, retention, discovery,
and external trust anchors without changing this result ontology.
