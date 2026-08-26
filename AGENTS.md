# Motif Balance agent router

Motif Balance is a standalone public software owner. Read the smallest authority
that governs the change:

| Need | Authority |
| --- | --- |
| Ownership or dependency direction | `ARCHITECTURE.md` |
| Schemas, score meaning, or search invariants | `DESIGN.md` |
| Determinism, artifact integrity, or limits | `RELIABILITY.md` |
| Inputs, paths, public data, or release posture | `SECURITY.md` |
| User concepts and journeys | `docs/index.md` |

## Working rules

- Keep reusable behavior here. Study questions, evidence, and claim decisions
  belong to Research Studies; manuscript selection and composition belong to
  `manufold`.
- Do not import neighboring repositories or depend on workspace-relative paths.
- Public models are strict and immutable. Add a failing contract or negative-
  path test before changing behavior.
- Keep scoring, search, and selection distinct. Selection must not mutate a
  candidate after evaluation.
- Treat every tracked file and built artifact as potentially public. Use only
  short synthetic examples.

## Completion gate

Run targeted checks while editing. Before declaring a repository change
complete, run:

```bash
bash ./scripts/agent-preflight --strict
bash ./scripts/agent-verify
```

The same verification endpoint runs in CI.
