from __future__ import annotations

from html import escape

from pydantic import Field, model_validator

from motif_balance.model import FrozenModel

from .limits import MAX_CATALOG_ENTRIES
from .model import ResultInspection


class CatalogEntry(FrozenModel):
    entry_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    subject_kind: str
    integrity_state: str
    problem_id: str
    run_id: str
    bundle_id: str
    workspace_id: str | None
    motif_ids: tuple[str, ...]
    length: int
    delivered_count: int
    score_min: float
    score_max: float
    distance_status: str
    search_completion: str
    package_version: str
    scoring_semantics: str
    objective_semantics: str
    tie_break_semantics: str

    @model_validator(mode="after")
    def validate_summary(self) -> CatalogEntry:
        if (self.subject_kind == "execution") != (self.workspace_id is not None):
            raise ValueError("catalog execution entries require a workspace identity")
        if self.score_min > self.score_max:
            raise ValueError("catalog score range is inverted")
        if not self.motif_ids or len(self.motif_ids) != len(set(self.motif_ids)):
            raise ValueError("catalog motif identifiers must be nonempty and unique")
        return self


class ResultCatalog(FrozenModel):
    schema_version: str = "motif-balance.result-catalog/v2"
    entries: tuple[CatalogEntry, ...]

    @model_validator(mode="after")
    def validate_entries(self) -> ResultCatalog:
        ids = tuple(entry.entry_id for entry in self.entries)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("catalog entry identifiers must be unique and sorted")
        if not ids or len(ids) > MAX_CATALOG_ENTRIES:
            raise ValueError(f"catalog must contain 1..{MAX_CATALOG_ENTRIES} entries")
        return self


def build_catalog(entries: dict[str, ResultInspection]) -> ResultCatalog:
    return ResultCatalog(
        entries=tuple(
            CatalogEntry(
                entry_id=entry_id,
                subject_kind=inspection.subject_kind,
                integrity_state=inspection.integrity.state,
                problem_id=inspection.problem.problem_id,
                run_id=inspection.run.run_id,
                bundle_id=inspection.run.bundle_id,
                workspace_id=(
                    inspection.execution.workspace_id if inspection.execution is not None else None
                ),
                motif_ids=tuple(motif.motif_id for motif in inspection.problem.motifs),
                length=inspection.problem.length,
                delivered_count=inspection.delivery.delivered_count,
                score_min=inspection.portfolio.score_min,
                score_max=inspection.portfolio.score_max,
                distance_status=inspection.portfolio.distance.status,
                search_completion=inspection.search.completion,
                package_version=inspection.run.package_version,
                scoring_semantics=inspection.problem.scoring_semantics,
                objective_semantics=inspection.problem.objective_semantics,
                tie_break_semantics=inspection.problem.tie_break_semantics,
            )
            for entry_id, inspection in sorted(entries.items())
        )
    )


def render_catalog_html(value: ResultCatalog) -> bytes:
    rows = "\n".join(
        "<tr>"
        f"<td>{escape(entry.entry_id)}</td><td>{escape(entry.subject_kind)}</td>"
        f"<td>{escape(entry.integrity_state)}</td><td><code>{escape(entry.problem_id)}</code></td>"
        f"<td>{escape(', '.join(entry.motif_ids))}</td><td>{entry.delivered_count}</td>"
        f"<td>{entry.score_min:.17g} .. {entry.score_max:.17g}</td>"
        f"<td>{escape(entry.distance_status)}</td><td>{escape(entry.search_completion)}</td>"
        "</tr>"
        for entry in value.entries
    )
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Motif Balance integration catalog</title><style>
body{{margin:0;background:#fbfcfa;color:#172021;font:16px/1.5 system-ui,sans-serif}}
main{{max-width:1280px;margin:auto;padding:2.5rem 1rem 5rem}}.table-wrap{{overflow-x:auto}}
table{{border-collapse:collapse;width:max-content;min-width:64rem;font-size:.88rem}}
th{{text-align:left;color:#5b6667}}
th,td{{border-bottom:1px solid #d9dfdd;padding:.55rem;vertical-align:top}}
code{{font:.82rem/1.4 ui-monospace,monospace}}
</style></head><body><main><h1>Motif Balance integration catalog</h1>
<p>Explicit current results only. This developer surface does not rank results,
define a cohort, or accept evidence.</p>
<div class="table-wrap"><table><thead><tr>
<th>Entry</th><th>Kind</th><th>Integrity</th><th>Problem</th><th>Motifs</th>
<th>Count</th><th>Score range</th><th>Distance</th><th>Completion</th>
</tr></thead><tbody>{rows}</tbody></table></div>
</main></body></html>"""
    return document.encode("utf-8")
