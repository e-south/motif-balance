# Technical-note evidence fixtures

This directory contains sanitized migration fixtures, not accepted scientific evidence. The
`scoring-parity-v1.json` record pins the smallest Cruncher Sample scoring comparison used to
classify the standalone contract. Research Studies owns evidence acceptance and manuscript claim
gates.

The fixture deliberately separates deterministic scoring parity from stochastic optimizer parity.
The latter is not asserted because RNG call order, proposal targeting, and legacy post-selection
polish/trim are separate behaviors.
