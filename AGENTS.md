# Repository guidance

Start with the document that governs the change:

- [Architecture](ARCHITECTURE.md) defines module responsibilities and dependencies.
- [Design contracts](DESIGN.md) defines scoring, search and selection invariants.
- [Reliability](RELIABILITY.md) defines reproducibility and artifact verification.
- [Security](SECURITY.md) defines input handling and publication safeguards.
- [Documentation](docs/README.md) routes user tasks and integration references.

## Working rules

Keep reusable sequence-design behavior in this package. Data collection,
experiment comparisons and manuscript composition belong in the consuming
project. Do not import neighboring repositories or depend on workspace paths.

Public models are strict and immutable. Add a failing contract or invalid-input
test before changing behavior. Keep scoring, search and selection separate;
selection must not change an evaluated sequence or its scores. Preserve existing
changes in the working tree and keep refactors separate from changes to the method.

Treat tracked files and distributions as public. Examples may use synthetic
models or explicitly attributed, redistributable biological models. Keep private
sequences, credentials and machine-local paths outside the repository.

## Verification

Run targeted checks while editing. Before completing a repository change, run
from the repository root:

```bash
bash ./scripts/preflight --strict
bash ./scripts/verify
```

[Contributing](CONTRIBUTING.md) describes the development workflow and review requirements.
