---
doc_id: motif-balance-concepts
title: How balanced motif design works
intent: Explain the design objective before its algorithms and output records.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: explanation
---

# How balanced motif design works

A motif model describes base preferences along a short DNA site. Scanning finds
where that model matches an existing sequence. Design reverses the task: supply
several models and an available length, then search for DNA with a strong match
to every desired model. Their best matches may share positions when space is
limited.

## One objective for desired and unwanted matches

For each motif, scan every valid position on the allowed strands and keep its
highest log-odds score. Subtract that motif's minimum possible site score, then
divide by the difference between its maximum and minimum site scores. This
puts the strongest match on a model-relative zero-to-one scale, called
**attainment**. [Methods](methods.md#scoring-a-candidate) gives the formula.

A `seek` requirement favors high attainment. An `avoid` requirement favors low
attainment of the strongest unwanted match anywhere in the sequence. Its
**satisfaction** is one minus that attainment. The overall **balance** is the
lowest satisfaction:

```text
satisfaction = attainment          for seek
satisfaction = 1 − attainment      for avoid
balance = minimum satisfaction across requirements
```

A strong match to one desired motif cannot compensate for a weak match to
another. Two desired attainments of 0.9 and 0.5 give balance 0.5; attainments
of 0.7 and 0.7 give balance 0.7. If a desired motif attains 0.8 and an unwanted
motif attains 0.3, their satisfactions are 0.8 and 0.7, also giving balance 0.7.
Avoidance is a trade-off in this objective, not an enforced maximum score.

## Search edits DNA and rescans the result

Search changes nucleotide identities while keeping sequence length fixed.
Every new candidate is rescanned, so the strongest matches can change their
positions, strands and overlap. The matching boxes are annotations of the
sequence, not independent objects moved by the optimizer.

The default search enumerates all sequences if the evaluation budget permits.
Otherwise it explores several starting sequences using annealed local search.
A candidate evaluation scans the entire sequence for every motif; a four-base
trial at one coordinate consumes four evaluations. The running best records
every evaluated candidate, including proposals not adopted for further search.

## Choose sequences for comparison

A design returns the requested number of ranked sequences, optionally subject
to a minimum sequence difference. To select distinct arrangements instead, use
[collections](choose-alternatives.md), which groups the selected motif matches
by order, orientation and interval relationships. These are different ways to
choose candidates for experimental comparison.

The scores quantify agreement with supplied models. Regulatory activity also
depends on context and must be measured experimentally. A bounded search gives
the best candidates found within its budget; only complete enumeration proves
an optimum. Read [interpretation](interpreting-results.md) for result fields
and [limitations](limitations.md) before drawing biological conclusions.
