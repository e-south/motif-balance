from __future__ import annotations

import base64
import hashlib
import zipfile
from pathlib import Path

import pytest

from motif_balance import (
    DesignSpec,
    MotifSpecification,
    Portfolio,
    design,
    score,
)
from motif_balance.constants import PACKAGE_VERSION
from motif_balance.errors import ArtifactError, IncompatibleDesign, InvalidDesign
from motif_balance.execution import execute_design_workspace, verify_execution_workspace
from motif_balance.formats.design import load_design_spec


@pytest.mark.parametrize("fault", ("schema", "scoring", "objective", "tie_break", "motif"))
@pytest.mark.parametrize("operation", ("score", "design"))
def test_public_operations_reject_retired_contracts_in_copied_models(
    pairwise_spec: DesignSpec, fault: str, operation: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    if fault == "motif":
        motifs = tuple(
            motif.model_copy(update={"schema_version": "motif-model/v1"})
            for motif in pairwise_spec.scored_motifs
        )
        forged = pairwise_spec.model_copy(
            update={
                "specifications": tuple(
                    MotifSpecification(motif=motif, direction="seek") for motif in motifs
                )
            }
        )
    else:
        field, value = {
            "schema": ("schema_version", "design-spec/v1"),
            "scoring": ("scoring_semantics", "normalized_llr_v1"),
            "objective": ("objective_semantics", "weakest_score_v1"),
            "tie_break": ("tie_break_semantics", "unknown_rule"),
        }[fault]
        forged = pairwise_spec.model_copy(update={field: value})
    monkeypatch.setattr(
        "motif_balance.compile._compile_motif",
        lambda *_: pytest.fail("unsupported contract reached motif compilation"),
    )
    with pytest.raises(IncompatibleDesign, match=r"[Uu]nsupported"):
        if operation == "score":
            score("A" * forged.length, forged)
        else:
            design(forged)


def _write_design(path: Path, spec: DesignSpec) -> None:
    path.write_text(spec.model_dump_json())


@pytest.mark.parametrize("operation", ("score", "design"))
@pytest.mark.parametrize("fault", ("budget", "boolean", "direction", "probabilities"))
def test_copied_invalid_requests_fail_before_matrix_compilation(
    pairwise_spec: DesignSpec, operation: str, fault: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    if fault in ("budget", "boolean"):
        forged = pairwise_spec.model_copy(
            update={"evaluations": 0} if fault == "budget" else {"seed": True}
        )
    else:
        first = pairwise_spec.specifications[0]
        if fault == "direction":
            first = first.model_copy(update={"direction": "typo"})
        else:
            motif = first.motif.model_copy(
                update={
                    "probabilities": tuple((0.7, 0.7, 0.1, 0.1) for _ in range(first.motif.width))
                }
            )
            first = first.model_copy(update={"motif": motif})
        forged = pairwise_spec.model_copy(
            update={"specifications": (first, *pairwise_spec.specifications[1:])}
        )
    monkeypatch.setattr(
        "motif_balance.compile._compile_motif",
        lambda *_: pytest.fail("invalid request reached matrix compilation"),
    )
    with pytest.raises(IncompatibleDesign):
        score("AAAA", forged) if operation == "score" else design(forged)


@pytest.mark.parametrize("operation", ("pair", "joint"))
def test_assessment_rejects_copied_invalid_probabilities_before_arrays(
    pairwise_spec: DesignSpec, operation: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from motif_balance.assessment import assess_motifs, assess_pair

    left, right = pairwise_spec.scored_motifs
    left = left.model_copy(update={"probabilities": ((0.7, 0.7, 0.1, 0.1),) * left.width})
    monkeypatch.setattr(
        "motif_balance.compile.np.asarray",
        lambda *_args, **_kwargs: pytest.fail("invalid motif reached array allocation"),
    )
    with pytest.raises(IncompatibleDesign):
        if operation == "pair":
            assess_pair(left, right, length=4)
        else:
            assess_motifs((left, right), length=4)


def _wheel(
    path: Path,
    *,
    metadata: str | None,
    include_package: bool = False,
    corrupt_record: str | None = None,
    bad_entry_point: bool = False,
) -> None:
    entries: dict[str, bytes] = {}
    dist_info = "package.dist-info/"
    if metadata is not None:
        entries[f"{dist_info}METADATA"] = metadata.encode()
        entries[f"{dist_info}WHEEL"] = b"Wheel-Version: 1.0\n"
        entries[f"{dist_info}entry_points.txt"] = (
            b"[console_scripts]\nmotif-balance = other:app\n"
            if bad_entry_point
            else b"[console_scripts]\nmotif-balance = motif_balance.cli:app\n"
        )
    if include_package:
        entries["motif_balance/__init__.py"] = b""
    if metadata is not None:
        record = "".join(
            f"{name},sha256={base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b'=').decode()},{len(payload)}\n"
            for name, payload in sorted(entries.items())
        )
        record += f"{dist_info}RECORD,,\n"
        if corrupt_record == "malformed":
            record = "malformed\n"
        elif corrupt_record == "digest":
            record = record.replace("sha256=", f"sha256={'0' * 43}", 1)
        entries[f"{dist_info}RECORD"] = record.encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)


def test_portfolio_replay_rejects_mutated_provenance_and_identity(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    portfolio = design(pairwise_spec)
    assert portfolio.to_fasta().startswith(">candidate-")

    mutations = (
        portfolio.manifest.model_copy(update={"package_version": "substituted"}),
        portfolio.manifest.model_copy(update={"problem_id": "problem-" + "0" * 24}),
        portfolio.manifest.model_copy(update={"run_id": "run-" + "0" * 24}),
        portfolio.manifest.model_copy(update={"rng": "substituted"}),
    )
    messages = (
        "package provenance",
        "problem identity",
        "run identity",
        "search provenance",
    )
    for index, (manifest, message) in enumerate(zip(mutations, messages, strict=True)):
        changed = portfolio.model_copy(update={"manifest": manifest})
        with pytest.raises(ArtifactError, match=message):
            changed.write(tmp_path / f"result-{index}")

    candidate = portfolio.candidates[0].model_copy(update={"candidate_id": "candidate-" + "0" * 16})
    changed_candidates = (candidate, *portfolio.candidates[1:])
    changed = Portfolio.model_validate(
        portfolio.model_dump(mode="python") | {"candidates": changed_candidates}
    )
    with pytest.raises(ArtifactError, match="candidate identity mismatch"):
        changed.write(tmp_path / "changed-candidate")


def test_load_spec_refuses_symbolic_links_and_nonstring_motif_ids(tmp_path: Path) -> None:
    target = tmp_path / "target.yaml"
    target.write_text("motifs: {}\nlength: 1\ncount: 1\nevaluations: 1\n")
    link = tmp_path / "link.yaml"
    link.symlink_to(target)
    with pytest.raises(InvalidDesign, match="symbolic-link"):
        load_design_spec(link)

    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(
        "schema_version: design-spec/v3\nspecifications:\n"
        "  - motif_id: 1\n    motif: {}\n    direction: seek\n"
        "length: 1\ncount: 1\nevaluations: 1\n"
    )
    with pytest.raises(InvalidDesign, match="motif_id must be a string"):
        load_design_spec(invalid)


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("not_zip", "valid wheel archive"),
        ("no_metadata", "wheel metadata record"),
        ("wrong_identity", "identity does not match"),
        ("no_package", "does not contain the motif_balance package"),
        ("bad_record", "RECORD is malformed"),
        ("record_digest", "RECORD mismatch"),
        ("bad_entry", "console entry point"),
    ],
)
def test_execute_rejects_invalid_wheel_artifacts_before_design(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
    kind: str,
    message: str,
) -> None:
    specification = tmp_path / "design.yaml"
    _write_design(specification, pairwise_spec)
    release = tmp_path / f"motif_balance-{PACKAGE_VERSION}-py3-none-any.whl"
    if kind == "not_zip":
        release.write_bytes(b"not a zip archive")
    elif kind == "no_metadata":
        _wheel(release, metadata=None, include_package=True)
    elif kind == "wrong_identity":
        _wheel(
            release,
            metadata=f"Metadata-Version: 2.4\nName: other\nVersion: {PACKAGE_VERSION}\n",
            include_package=True,
        )
    elif kind == "no_package":
        _wheel(
            release,
            metadata=f"Metadata-Version: 2.4\nName: motif-balance\nVersion: {PACKAGE_VERSION}\n",
        )
    else:
        _wheel(
            release,
            metadata=f"Metadata-Version: 2.4\nName: motif-balance\nVersion: {PACKAGE_VERSION}\n",
            include_package=True,
            corrupt_record="malformed" if kind == "bad_record" else None,
            bad_entry_point=kind == "bad_entry",
        )
        if kind == "record_digest":
            _wheel(
                release,
                metadata=(
                    f"Metadata-Version: 2.4\nName: motif-balance\nVersion: {PACKAGE_VERSION}\n"
                ),
                include_package=True,
                corrupt_record="digest",
            )

    with pytest.raises(ArtifactError, match=message):
        execute_design_workspace(
            specification,
            tmp_path / "execution",
            producer_revision="a" * 40,
            release_artifact=release,
        )


def test_execute_rejects_symlinked_release_and_invalid_revision(
    tmp_path: Path,
    pairwise_spec: DesignSpec,
) -> None:
    specification = tmp_path / "design.yaml"
    _write_design(specification, pairwise_spec)
    target = tmp_path / "target.whl"
    target.write_bytes(b"wheel")
    link = tmp_path / "release.whl"
    link.symlink_to(target)

    with pytest.raises(ArtifactError, match="symbolic link"):
        execute_design_workspace(
            specification,
            tmp_path / "execution",
            producer_revision="a" * 40,
            release_artifact=link,
        )
    with pytest.raises(ArtifactError, match="40-character"):
        execute_design_workspace(
            specification,
            tmp_path / "execution",
            producer_revision="not-a-revision",
            release_artifact=target,
        )


def test_verify_execution_rejects_a_missing_workspace(tmp_path: Path) -> None:
    with pytest.raises(ArtifactError, match="missing or unsafe"):
        verify_execution_workspace(
            tmp_path / "missing",
            expected_workspace_id="execution-" + "0" * 24,
            expected_receipt_sha256="0" * 64,
            expected_release_sha256="0" * 64,
            expected_producer_revision="0" * 40,
        )
