"""
--------------------------------------------------------------------------------
motif-balance
src/motif_balance/variants/expansion.py

Bounded expansion that retains every qualifying sequence it evaluates.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import math
from collections import deque
from typing import Literal, cast

from motif_balance.compile import compile_scoring
from motif_balance.constants import BUILD_LOCK_SHA256, PACKAGE_VERSION, RUNTIME_CONTRACT
from motif_balance.formats.structured import load_json_unique
from motif_balance.model import DesignSpec
from motif_balance.model.sequence_expansion import ExpansionTrial, SequenceExpansion, sequence_code
from motif_balance.scoring import evaluate

from .api import _changes, _replay_equal

MAX_OPERATIONS = 1_000_000_000
MAX_CACHED_BASES = 32_000_000
MAX_MATCH_RECORDS = 50_000
MAX_HANDOFF_BYTES = 64_000_000


def _output_bound(spec: DesignSpec, cap: int, budget: int) -> int:
    """Conservative pretty-JSON size, including DNA within every motif match.

    Allow extra indentation when the record is nested in a collection. Full
    evaluations occur only for retained sequences and the separately saved parent;
    trial records contain one edit, not another copy of the sequence and matches.
    """
    match_bytes = sum(1024 + len(s.motif.motif_id) + s.motif.width for s in spec.specifications)
    return (
        65536
        + 8 * len(spec.model_dump_json(indent=2).encode())
        + 32 * spec.length
        + (min(cap, budget) + 1) * (768 + spec.length + match_bytes)
        + (budget - 1) * 512
    )


def _admit(
    spec: DesignSpec, floor: float, cap: int, budget: int, mask: tuple[bool, ...] | None
) -> int:
    """Validate work, live memory, and output bounds before calling the scorer."""
    if type(cap) is not int or not 1 <= cap <= 1024:
        raise ValueError("max_variants must be an integer from 1 through 1024")
    if type(budget) is not int or not 1 <= budget <= 100_000:
        raise ValueError("max_evaluations must be an integer from 1 through 100000")
    if (
        isinstance(floor, bool)
        or not isinstance(floor, (float, int))
        or not math.isfinite(floor)
        or not 0 <= floor <= 1
    ):
        raise ValueError("min_balance must be finite and between zero and one")
    if mask is not None and (
        not isinstance(mask, tuple)
        or len(mask) != spec.length
        or any(type(v) is not bool for v in mask)
    ):
        raise ValueError("editable_mask must contain one boolean per DNA position")
    if not any(s.direction == "seek" for s in spec.specifications):
        raise ValueError("expansion requires at least one desired model")
    cost = sum(s.motif.width * (spec.length - s.motif.width + 1) for s in spec.specifications)
    cost *= 2 if spec.strands == "both" else 1
    if (
        budget * cost > MAX_OPERATIONS
        or budget * spec.length > MAX_CACHED_BASES
        or cap * len(spec.specifications) > MAX_MATCH_RECORDS
        or _output_bound(spec, cap, budget) > MAX_HANDOFF_BYTES
    ):
        raise ValueError(
            "expansion exceeds bounded work, cache, or output limits; "
            "reduce the evaluation or variant allowance"
        )
    return cost


def expand(
    sequence: str,
    spec: DesignSpec,
    *,
    min_balance: float,
    max_variants: int = 256,
    max_evaluations: int = 4096,
    editable_mask: tuple[bool, ...] | None = None,
) -> SequenceExpansion:
    """Explore qualifying one-base neighbours and return every passing evaluation.

    Breadth-first traversal visits accepted sequences in discovery order, positions
    left to right, and alternatives in A/C/G/T order. Sites and frozen bases are
    always compared with the original parent. There is no ambiguity template.
    Exhausting this connected frontier does not exclude disconnected solutions.
    """
    spec = DesignSpec.model_validate(spec.model_dump(mode="python", warnings=False))
    cost = _admit(spec, min_balance, max_variants, max_evaluations, editable_mask)
    problem = compile_scoring(spec)
    parent = evaluate(sequence, problem)
    if parent.balance_score < min_balance - 1e-12:
        raise ValueError("parent balance is below min_balance")
    positions = tuple(
        i
        for i in range(spec.length)
        if (
            editable_mask[i]
            if editable_mask is not None
            else any(m.spec_direction == "seek" and m.start <= i < m.end for m in parent.matches)
        )
    )
    variants = [parent]
    trials: list[ExpansionTrial] = []
    queue = deque([0])
    seen = {sequence_code(parent.sequence)}
    stop: Literal["variant_limit", "evaluation_limit", "frontier_exhausted"] = "frontier_exhausted"
    finished = False
    while queue and not finished:
        source_index = queue.popleft()
        source = variants[source_index].sequence
        source_code = sequence_code(source)
        for position in positions:
            shift = 2 * (spec.length - position - 1)
            for digit, base in enumerate("ACGT"):
                code = (source_code & ~(3 << shift)) | (digit << shift)
                if code in seen:
                    continue
                if len(variants) >= max_variants or len(trials) + 1 >= max_evaluations:
                    stop = "variant_limit" if len(variants) >= max_variants else "evaluation_limit"
                    finished = True
                    break
                seen.add(code)
                candidate = source[:position] + base + source[position + 1 :]
                value = evaluate(candidate, problem)
                _, moved = _changes(parent, value)
                status: Literal["retained", "below_floor", "site_changed"] = (
                    "site_changed"
                    if moved
                    else "below_floor"
                    if value.balance_score < min_balance - 1e-12
                    else "retained"
                )
                if status == "retained":
                    queue.append(len(variants))
                    variants.append(value)
                trials.append(
                    ExpansionTrial(
                        source_index=source_index,
                        position=position,
                        base=cast(Literal["A", "C", "G", "T"], base),
                        balance_score=value.balance_score,
                        status=status,
                    )
                )
            if finished:
                break
    return SequenceExpansion(
        package_version=PACKAGE_VERSION,
        runtime_contract=RUNTIME_CONTRACT,
        build_lock_sha256=BUILD_LOCK_SHA256,
        spec=spec,
        parent=parent,
        min_balance=min_balance,
        max_variants=max_variants,
        max_evaluations=max_evaluations,
        editable_positions=positions,
        variants=tuple(variants),
        trials=tuple(trials),
        score_operations=(1 + len(trials)) * cost,
        stop_reason=stop,
    )


def verify_expansion(result: SequenceExpansion) -> SequenceExpansion:
    """Replay settings, decisions, identities, scores, sites, and stopping reason."""
    result = SequenceExpansion.model_validate(result.model_dump(mode="python", warnings=False))
    expected = expand(
        result.parent.sequence,
        result.spec,
        min_balance=result.min_balance,
        max_variants=result.max_variants,
        max_evaluations=result.max_evaluations,
        editable_mask=tuple(i in result.editable_positions for i in range(result.spec.length)),
    )
    declarations = {"package_version", "build_lock_sha256"}
    if not _replay_equal(
        result.model_dump(mode="json", exclude=declarations),
        expected.model_dump(mode="json", exclude=declarations),
    ):
        raise ValueError("expansion disagrees with deterministic replay")
    return result


def load_expansion(raw: str | bytes) -> SequenceExpansion:
    if not isinstance(raw, (str, bytes)) or len(raw) > MAX_HANDOFF_BYTES:
        raise ValueError("expansion JSON must be text or bytes within the 64 MB limit")
    encoded = raw.encode() if isinstance(raw, str) else raw
    if len(encoded) > MAX_HANDOFF_BYTES:
        raise ValueError("expansion exceeds the 64 MB limit")
    return verify_expansion(SequenceExpansion.model_validate(load_json_unique(encoded)))
