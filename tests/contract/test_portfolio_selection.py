"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_portfolio_selection.py

The public supplied-pool journey returns full, replayable constrained sets.

Module Author(s): Eric J. South
Dunlop Lab
--------------------------------------------------------------------------------
"""

from itertools import combinations, product

import pytest
from pydantic import ValidationError

from motif_balance import DesignSpec, MotifModel, MotifSpecification


def request(*, length=4, strands="both", words=("AC", "CG"), count=1):
    return DesignSpec(
        schema_version="design-spec/v3",
        length=length,
        strands=strands,
        count=count,
        seed=7,
        evaluations=max(count, 1),
        specifications=tuple(
            MotifSpecification(
                direction="seek",
                motif=MotifModel(
                    motif_id=f"synthetic_{i}",
                    background=(0.25,) * 4,
                    probabilities=tuple(
                        tuple(0.7 if b == preferred else 0.1 for b in "ACGT") for preferred in word
                    ),
                ),
            )
            for i, word in enumerate(words)
        ),
    )


def policy(**updates):
    from motif_balance.model.selection import PortfolioPolicy

    return PortfolioPolicy(
        **{
            "count": 2,
            "separation": "selected_footprint",
            "min_distance": 0.2,
            "equivalence": "reverse_complement",
            "architectures": "distinct",
            **updates,
        }
    )


def test_public_selection_replays_literals_and_separates_generation_count():
    from motif_balance.alternatives import select_portfolio, verify_portfolio_selection
    from motif_balance.model.selection import PortfolioSelection

    spec = request(length=2, strands="forward", words=("A", "C"), count=17)
    words = ["AC", "CA", "AA", "AC"]
    result = select_portfolio(words, spec, policy(equivalence="forward"))
    assert words == ["AC", "CA", "AA", "AC"]
    assert result.spec == spec and result.spec.count == 17 and result.policy.count == 2
    assert result.status == "optimal" and result.quality == 1
    assert result.delivered_count == 2
    assert [m.evaluation.sequence for m in result.members] == ["AC", "CA"]
    assert result.minimum_separation == 1
    assert result.input_records == 4 and result.sequence_classes == 3
    assert result.scoring_evaluations == 3 and result.search_evaluations == 0
    assert result == select_portfolio(list(reversed(words)), spec, result.policy)
    copy = PortfolioSelection.model_validate_json(result.model_dump_json())
    assert verify_portfolio_selection(copy, words) == copy
    with pytest.raises(ValueError, match="replay"):
        verify_portfolio_selection(copy, ["AC", "CA", "AA"])


@pytest.mark.parametrize("update", ({"count": 0}, {"work_limit": -1}, {"min_distance": -0.1}))
def test_copied_invalid_policy_fails_before_pool_admission(update, monkeypatch):
    from motif_balance.alternatives import select_portfolio

    monkeypatch.setattr(
        "motif_balance.alternatives.portfolio.prepare_pool",
        lambda *_: pytest.fail("invalid policy reached pool admission"),
    )
    with pytest.raises(ValueError):
        select_portfolio(["ACGT"], request(), policy().model_copy(update=update))


def test_flank_only_changes_cannot_satisfy_footprint_separation():
    from motif_balance.alternatives import select_portfolio

    spec = request(length=6, strands="forward")
    words = ("ACGAAA", "ACGCCC")
    footprint = select_portfolio(
        words, spec, policy(equivalence="forward", architectures="unrestricted")
    )
    hamming = select_portfolio(
        words,
        spec,
        policy(equivalence="forward", separation="hamming", architectures="unrestricted"),
    )
    assert footprint.status == "pool_infeasible" and footprint.quality is None
    assert footprint.members == () and footprint.delivered_count == 0
    assert hamming.status == "optimal" and hamming.minimum_separation == 0.5


def test_rc_equivalence_cannot_create_an_additional_candidate():
    from motif_balance.alternatives import select_portfolio

    result = select_portfolio(("ACGA", "TCGT"), request(), policy())
    assert result.sequence_classes == result.scoring_evaluations == 1
    assert result.status == "pool_infeasible" and result.quality is None


def test_necessary_architecture_bound_fails_before_scoring(monkeypatch):
    from motif_balance.alternatives import portfolio

    monkeypatch.setattr(portfolio, "evaluate", lambda *_: pytest.fail("bound ignored"))
    result = portfolio.select_portfolio(
        ("AC", "CG", "GA", "TT"), request(length=2), policy(count=4)
    )
    assert result.status == "architecture_bound"
    assert result.architecture_upper_bound == 2 and result.quality is None
    assert result.scoring_evaluations == result.selection_work == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("count", True),
        ("count", "2"),
        ("count", 0),
        ("min_distance", float("nan")),
        ("min_distance", 1.1),
        ("work_limit", 0),
        ("work_limit", 1_000_001),
        ("equivalence", "automatic"),
        ("architectures", True),
        ("unknown", 1),
    ],
)
def test_policy_rejects_ambiguous_or_unbounded_inputs(field, value):
    with pytest.raises(ValidationError):
        policy(**{field: value})


def test_selection_refuses_mismatched_strands_and_distance_semantics():
    from motif_balance.alternatives import select_portfolio

    with pytest.raises(ValueError, match="equivalence"):
        select_portfolio(("ACGA",), request(), policy(equivalence="forward"))
    payload = request().model_dump(mode="python")
    payload["min_distance"] = 0.3
    with pytest.raises(ValueError, match="distance"):
        select_portfolio(("ACGA",), DesignSpec.model_validate(payload), policy())


def test_pool_and_distance_admission_precede_scoring_and_quadratic_preparation(monkeypatch):
    from motif_balance.alternatives import portfolio

    monkeypatch.setattr(portfolio, "evaluate", lambda *_: pytest.fail("unadmitted scoring"))
    with pytest.raises(ValueError, match="distance"):
        portfolio.select_portfolio(("ACGA", "CAGA"), request(), policy(distance_base_budget=1))
    for words in (("AC",), ("acga",), ("ACGN",), iter(("ACGA",))):
        with pytest.raises(ValueError, match=r"pool|sequence"):
            portfolio.select_portfolio(words, request(), policy())


def test_quality_is_undefined_until_a_full_witness_exists():
    from motif_balance.alternatives import select_portfolio

    words = ("AC", "AG", "AT", "CA")
    spec = request(length=2, strands="forward", words=("A", "C"))
    early = select_portfolio(
        words,
        spec,
        policy(equivalence="forward", work_limit=1, architectures="unrestricted", min_distance=0.0),
    )
    found = select_portfolio(
        words,
        spec,
        policy(equivalence="forward", work_limit=3, architectures="unrestricted", min_distance=0.0),
    )
    assert early.status == "unresolved" and early.quality is None and not early.members
    assert found.status == "feasible" and found.quality == 1 and len(found.members) == 2


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_public_results_match_literal_small_pool_subset_oracle(count):
    from math import fsum

    from motif_balance.alternatives import select_portfolio
    from motif_balance.compile import compile_scoring
    from motif_balance.scoring import evaluate

    words = tuple("".join(w) for w in product("AC", repeat=3))
    spec = request(length=3, strands="forward", words=("A", "C"))
    evaluated = {w: evaluate(w, compile_scoring(spec)) for w in words}
    # Independent forward-only one-base models: first A and first C (or 0 if
    # absent) are the selected sites. No product geometry or distance helper.
    sites = {w: {max(w.find("A"), 0), max(w.find("C"), 0)} for w in words}
    geometry = {w: max(w.find("C"), 0) - max(w.find("A"), 0) for w in words}
    valid = []
    for subset in combinations(words, count):
        if any(
            geometry[a] == geometry[b]
            or sum(a[i] != b[i] for i in sites[a] | sites[b]) / len(sites[a] | sites[b]) < 0.2
            for a, b in combinations(subset, 2)
        ):
            continue
        valid.append(subset)
    expected = (
        min(
            valid,
            key=lambda xs: (
                -min(evaluated[w].balance_score for w in xs),
                -fsum(evaluated[w].balance_score for w in xs),
                xs,
            ),
        )
        if valid
        else ()
    )
    result = select_portfolio(words, spec, policy(count=count, equivalence="forward"))
    assert tuple(sorted(m.evaluation.sequence for m in result.members)) == expected
    assert result.status == ("optimal" if expected else "pool_infeasible")


def test_same_architecture_variants_are_kept_until_constrained_selection():
    from motif_balance.alternatives import select_portfolio

    # AA and CC both select overlapping sites, yet are distinct strings needed
    # for this feasible four-member request. Do not prune either class member.
    words = ("AC", "CA", "AA", "CC")
    result = select_portfolio(
        words,
        request(length=2, strands="forward", words=("A", "C")),
        policy(
            count=4,
            equivalence="forward",
            architectures="unrestricted",
            min_distance=0.5,
            separation="hamming",
        ),
    )
    assert result.status == "optimal" and len(result.members) == 4
    assert result.sequence_classes == 4


@pytest.mark.parametrize(
    "change",
    [
        {"architecture_upper_bound": 999},
        {"distance_base_operations": 0},
        {"selection_work": 0},
        {
            "input_records": 1,
            "literal_sequences": 1,
            "sequence_classes": 1,
            "scoring_evaluations": 1,
        },
    ],
)
def test_serialized_selection_rejects_inconsistent_proof_and_work_fields(change):
    from motif_balance.alternatives import select_portfolio
    from motif_balance.model.selection import PortfolioSelection

    result = select_portfolio(
        ("AC", "CA"),
        request(length=2, strands="forward", words=("A", "C")),
        policy(equivalence="forward"),
    )
    with pytest.raises(ValidationError):
        PortfolioSelection.model_validate({**result.model_dump(mode="python"), **change})


def test_a_necessary_bound_cannot_be_claimed_when_it_does_not_rule_out_the_request():
    from motif_balance.alternatives import select_portfolio
    from motif_balance.model.base import _sha256
    from motif_balance.model.selection import PortfolioSelection

    result = select_portfolio(("AC", "CG", "GA", "TT"), request(length=2), policy(count=4))
    payload = result.model_dump(mode="python")
    payload["policy"] = policy(count=2)
    with pytest.raises(ValidationError, match="bound"):
        PortfolioSelection.model_validate(payload)
    assert result.request_digest == _sha256(result.spec.model_dump(mode="json"))


@pytest.mark.parametrize(
    "fault",
    [
        "request",
        "counts",
        "strand_counts",
        "work_limit",
        "quality",
        "missing_member",
        "duplicate",
        "identity",
        "geometry",
        "order",
        "pairs",
        "separation",
        "minimum",
    ],
)
def test_serialized_member_and_delivery_invariants(fault):
    from motif_balance.alternatives import select_portfolio
    from motif_balance.model.selection import PortfolioSelection

    result = select_portfolio(
        ("AC", "CA"),
        request(length=2, strands="forward", words=("A", "C")),
        policy(equivalence="forward"),
    )
    payload = result.model_dump(mode="python")
    if fault == "request":
        payload["request_digest"] = "0" * 64
    elif fault == "counts":
        payload["input_records"] = 0
    elif fault == "strand_counts":
        payload["input_records"] = payload["literal_sequences"] = 3
    elif fault == "work_limit":
        payload["selection_work"] = result.policy.work_limit + 1
    elif fault == "quality":
        payload["quality"] = None
    elif fault == "missing_member":
        payload["members"] = payload["members"][:1]
    elif fault == "duplicate":
        payload["members"] = (payload["members"][0],) * 2
    elif fault == "identity":
        payload["members"][0]["candidate_id"] = "candidate-" + "0" * 16
    elif fault == "geometry":
        payload["members"][0]["architecture"] = ()
    elif fault == "order":
        payload["members"] = tuple(reversed(payload["members"]))
    elif fault == "pairs":
        payload["separations"] = ()
    elif fault == "separation":
        payload["separations"][0]["value"] = 0.0
    else:
        payload["minimum_separation"] = 0.0
    with pytest.raises(ValidationError):
        PortfolioSelection.model_validate(payload)


def test_raw_dicts_are_not_implicit_policy_or_verified_result_adapters():
    from motif_balance.alternatives import select_portfolio, verify_portfolio_selection

    with pytest.raises(ValueError, match="typed"):
        select_portfolio(("ACGA",), request(), policy().model_dump())
    with pytest.raises(ValueError, match="typed"):
        verify_portfolio_selection({}, ("ACGA",))


def test_three_model_selection_has_no_unjustified_pair_architecture_bound():
    from motif_balance.alternatives import select_portfolio

    result = select_portfolio(
        ("ACG", "CGA"),
        request(length=3, strands="forward", words=("A", "C", "G")),
        policy(equivalence="forward"),
    )
    assert result.status == "optimal" and result.quality == 1.0
    assert result.architecture_upper_bound is None
    assert len(result.policy.policy_digest) == len(result.result_digest) == 64
