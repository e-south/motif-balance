---
doc_id: motif-balance-reproduce-paper
title: Reproduce the Motif Balance manuscript
intent: Reserve the public route for a future released evidence recipe.
audience:
  - users
  - integrators
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: how-to
journey:
  - verify
---

# Reproduce the Motif Balance manuscript

The manuscript evidence recipe is not released yet. This page is a route
placeholder, not a claim that the current package reproduces a paper.

Before this route becomes executable, a Research Studies release must publish a
versioned task cohort, motif digests, specifications, baselines, budgets, seeds,
expected candidate counts, accepted tables and plots, and checksums. The
manuscript workspace must then import only those accepted snapshots by digest.

The eventual reproduction command will consume released inputs through the
public `motif-balance` CLI and verify canonical bundles. It will not import a
Research Studies or `manufold` source tree, follow machine-local paths, or copy
private raw data into this repository.

Until those inputs exist, use [methods](methods.md) to review the software
contract and [limitations](limitations.md) to keep claims within scope.
