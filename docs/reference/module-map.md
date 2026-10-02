# Module responsibilities

Use this map to locate an operation before changing it. The
[architecture overview](../../ARCHITECTURE.md) explains the dependency direction.

```text
errors, constants, and model
  <- formats, compile, scoring, and assessment
  <- search, selection, alternatives, and variants
  <- api and artifacts
  <- receipt and execution
  <- inspection/{verify, project, render} and playback
  <- cli
```

## Find the implementation

| Operation | Modules |
| --- | --- |
| Define requests, models, scores, and result records | `model/`; shared literals in `constants.py` |
| Read external formats | `formats/` |
| Prepare log-odds matrices and evaluate DNA | `compile.py`, `scoring.py` |
| Assess shared-base preferences before search | `assessment/pair.py`, `joint.py`, and shared loss calculation in `terms.py` |
| Propose and accept sequence edits | `search/engine.py`, `moves.py`, `policy.py`, `initialization.py`, `greedy.py`, `uniform.py` |
| Record search progress and retained candidates | `search/recording.py`, `observation.py`, `retention.py` |
| Select a fixed-size sequence portfolio | `selection.py`; supplied-pool entry point in `alternatives/portfolio.py` |
| Rank site arrangements | `alternatives/api.py`, `pool.py`, `geometry.py` |
| Build checked degenerate products | `variants/api.py`, `bounds.py`, `collection.py` |
| Expand explicit sequence lists | `variants/expansion.py`, `expansion_collection.py` |
| Design, score, and save a portfolio | `api.py` |
| Encode, verify, and publish result bundles | `artifacts/encoding.py`, `decoding.py`, `snapshot.py`, `verification.py`, `publication.py` |
| Bind a run to its distribution and runtime | `receipt.py`, `execution/release.py`, `workspace_io.py`, `workspace.py` |
| Inspect saved results or a supplied candidate | `inspection/api.py`, `verify.py`, `project.py`, `supplied.py` |
| Draw candidates and pre-search preferences | `inspection/render/`, with projections from `inspection/candidate_model.py` and `inspection/assessment/` |
| Animate recorded searches | `playback/api.py`, `model.py`, `render.py`, `transition.py`, `media.py` |
| Prepare installed biological examples | `examples/preparation.py`, `download.py`, `profiles.py` |
| Adapt command-line arguments and files | `cli/` |

## Preserve the boundaries

- **Models and formats.** Immutable records reject unsupported fields. Models
  and constants import no higher layer. Readers parse inputs without choosing
  scoring or search rules.
- **Scoring and search.** `scoring.py` defines matching and public scores.
  `compile_scoring` checks motif widths and normalization; `compile_design` also
  checks requested count. Both use the same matrices and problem identity.
  Recording and retention do not alter search decisions or random draws.
- **Selection.** `selection.py` chooses unchanged, already-scored candidates.
  Arrangement ranking and distance-constrained selection operate on the supplied
  pool without starting a search. Each has its own selection rule.
- **Expansion.** Both variant operations reuse complete-sequence scoring and
  never call search or arrangement selection. Explicit expansion retains every
  passing evaluation. A degenerate product must pass for every encoded member;
  its preliminary fixed-site check can reject an addition but cannot accept it.
  Collection operations check parents and aggregate limits before work and keep
  each library separate. Loading a library replays its construction.
- **Files and execution.** Saved results retain inputs and checksums and are
  written atomically without replacing existing outputs. Runtime records identify
  the installed software separately from the scientific result.
- **Inspection and rendering.** Inspection verifies results and projects scores.
  Renderers draw those checked records without rescoring or searching. Inspection
  of supplied DNA does not imply a search was performed. Pre-search views show
  model preferences and placement losses, not a designed sequence.
- **Playback and CLI.** Playback verifies observations, binds saved states to the
  scoring problem, and interpolates drawings without inventing scores. CLI modules
  translate files and arguments into calls to these operations.

`scripts/check_architecture.py` enforces imports, including relative imports,
and rejects undeclared first-party modules. Update the map and matching checks
when introducing a responsibility. [Design contracts](../../DESIGN.md),
[reliability](../../RELIABILITY.md), and [security](../../SECURITY.md) define the
scoring, verification, and input-handling requirements.
