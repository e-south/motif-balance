"""Passive, bounded recording; never draws randomness or makes search decisions."""

from __future__ import annotations

import math
from typing import Literal, cast

from motif_balance.constants import MAX_SEARCH_OBSERVATION_BYTES
from motif_balance.model import DesignSpec, Evaluation
from motif_balance.model.search_observation import (
    ChainState,
    ObservationSpec,
    ObservedMoveCounts,
    SearchObservation,
    SearchSnapshot,
    TargetHit,
)

from .retention import QualityRetention


class SearchRecorder:
    def __init__(self, spec: DesignSpec, config: ObservationSpec) -> None:
        if spec.schema_version != "design-spec/v3":
            raise ValueError("search observations require directional design-spec/v3")
        projected_bases = (
            config.max_snapshots * 9
            + len(config.quality_thresholds) * config.max_sequences_per_threshold
        ) * (spec.length + sum(item.motif.width for item in spec.specifications))
        if projected_bases > 1_000_000:
            raise ValueError("search observation exceeds the snapshot base limit")
        # Include repeated identifiers and match metadata, not only DNA bases.
        evaluation_bytes = (
            1024
            + spec.length
            + sum(
                1024 + len(item.motif.motif_id.encode()) + item.motif.width
                for item in spec.specifications
            )
        )
        record_count = (
            config.max_snapshots * 9
            + len(config.quality_thresholds) * config.max_sequences_per_threshold
        )
        projected_bytes = (
            len(spec.model_dump_json().encode()) + 65_536 + record_count * evaluation_bytes
        )
        if projected_bytes > MAX_SEARCH_OBSERVATION_BYTES:
            raise ValueError("search observation exceeds the conservative byte limit")
        self.spec = spec
        self.config = config
        self.quality = QualityRetention(
            config.quality_thresholds, config.max_sequences_per_threshold
        )
        self.frames: list[SearchSnapshot] = []
        self.hits: dict[float, int | None] = dict.fromkeys(config.score_targets)
        self.counts = {
            move: dict.fromkeys(("attempted", "accepted", "changed", "improved", "decreased"), 0)
            for move in ("single", "block", "multi", "insertion")
        }
        self.interval = math.ceil(spec.evaluations / max(1, config.max_snapshots - 2))
        self.next_snapshot = self.interval

    def evaluated(self, result: Evaluation, count: int, *, is_new: bool) -> None:
        self.quality.record(result, is_new=is_new)
        for target, hit in self.hits.items():
            if hit is None and result.balance_score >= target:
                self.hits[target] = count

    def moved(self, move: str, accepted: bool, before: Evaluation, after: Evaluation) -> None:
        counts = self.counts[move]
        counts["attempted"] += 1
        counts["accepted"] += int(accepted)
        changed = accepted and before.sequence != after.sequence
        counts["changed"] += int(changed)
        counts["improved"] += int(changed and after.balance_score > before.balance_score)
        counts["decreased"] += int(changed and after.balance_score < before.balance_score)

    def snapshot(
        self,
        count: int,
        incumbent: Evaluation | None,
        states: tuple[Evaluation, ...],
        *,
        force: bool = False,
    ) -> None:
        if not force and count < self.next_snapshot:
            return
        if incumbent is None:
            raise ValueError("cannot observe a search before evaluation")
        frame = SearchSnapshot(
            evaluations=count,
            incumbent=incumbent,
            states=tuple(
                ChainState(chain_id=i, evaluation=state) for i, state in enumerate(states)
            ),
        )
        if self.frames and self.frames[-1].evaluations == count:
            self.frames[-1] = frame
        else:
            self.frames.append(frame)
        self.next_snapshot = (count // self.interval + 1) * self.interval
        if len(self.frames) > self.config.max_snapshots:
            raise ValueError("search observation exceeded its snapshot limit")

    def finish(
        self, *, engine: str, engine_version: str, evaluation_count: int
    ) -> SearchObservation:
        return SearchObservation(
            spec=self.spec,
            observation_spec=self.config,
            engine=engine,
            engine_version=engine_version,
            evaluation_count=evaluation_count,
            snapshots=tuple(self.frames),
            target_hits=tuple(
                TargetHit(target=target, first_evaluation=hit) for target, hit in self.hits.items()
            ),
            moves=tuple(
                ObservedMoveCounts(
                    move=cast(Literal["single", "block", "multi", "insertion"], move), **counts
                )
                for move, counts in self.counts.items()
            ),
            quality_samples=self.quality.finish(),
        )
