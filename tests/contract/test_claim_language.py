from __future__ import annotations

from re import Match

import pytest

import motif_balance
import motif_balance.claim_language as claim_language
from motif_balance.claim_language import ClaimFinding, check_claim_text


def _rule_ids(text: str) -> tuple[str, ...]:
    return tuple(finding.rule_id for finding in check_claim_text(text))


def test_claim_check_reports_known_prior_art_and_interpretation_hazards() -> None:
    text = """Motif Balance is the first inverse-design method based on PWMs.
This is the first tool to design sequences with multiple TFBSs.
We introduce the first motif-generating software.
Our novel normalization maps every motif to an attainable range.
The method returns the globally optimal sequence and the search converged.
The design achieves balanced binding affinity and predicts expression.
The motifs are physically superimposed and therefore co-bind.
"""

    findings = check_claim_text(text)

    assert all(isinstance(finding, ClaimFinding) for finding in findings)
    assert _rule_ids(text) == (
        "prior-art.first-pwm-inverse-design",
        "prior-art.first-multiple-tfbs-design",
        "prior-art.first-motif-generator",
        "prior-art.novel-normalization",
        "semantics.single-site-range",
        "search.global-optimality",
        "search.convergence",
        "biology.uncalibrated-affinity-or-outcome",
        "biology.uncalibrated-affinity-or-outcome",
        "biology.physical-superposition",
    )
    assert [finding.line for finding in findings] == [1, 2, 3, 4, 4, 5, 5, 6, 6, 7]
    assert findings[0].matched_text == "first inverse-design method based on PWMs"
    assert all(finding.rationale and finding.safer_wording for finding in findings)


def test_claim_check_respects_explicit_boundaries_and_supported_context() -> None:
    text = """This is not the first inverse design of DNA from PWMs.
Prior work by Martinez and Barr established PWM-informed inverse design.
Do not claim that this is the first tool for designing multiple TFBSs.
MATCH is prior art against calling relative score normalization novel.
The endpoints are theoretical single-site log-likelihood-ratio extrema.
Exhaustive enumeration of the complete sequence space proves the exact optimum.
Budget exhaustion is not convergence and does not establish global optimality.
PWM scores do not predict binding, occupancy, expression, or affinity.
An affinity-calibrated model may support a binding-affinity interpretation.
Model-defined shared-base compatibility is a sequence-score descriptor.
"First inverse design of regulatory DNA" is too broad.
"""

    assert check_claim_text(text) == ()


def test_claim_check_detects_broad_inverse_design_novelty_and_localizes_negation() -> None:
    text = (
        "Prior work is not claimed away. Motif Balance is the first inverse design of "
        "regulatory DNA."
    )

    findings = check_claim_text(text)

    assert tuple(finding.rule_id for finding in findings) == ("prior-art.first-pwm-inverse-design",)
    assert findings[0].matched_text == "first inverse design of regulatory DNA"
    assert findings[0].line == 1


def test_claim_check_covers_compact_hazard_phrasings() -> None:
    text = """This is the first PWM-based inverse design.
This is the first multiple-TFBS design.
The optimal candidate proves the method reached convergence.
Motif mixability establishes physical co-occupancy.
"""

    assert _rule_ids(text) == (
        "prior-art.first-pwm-inverse-design",
        "prior-art.first-multiple-tfbs-design",
        "search.global-optimality",
        "search.convergence",
        "biology.physical-superposition",
    )


@pytest.mark.parametrize(
    ("text", "rule_id"),
    [
        (
            "This wording is too broad. Motif Balance is the first inverse design of "
            "regulatory DNA.",
            "prior-art.first-pwm-inverse-design",
        ),
        (
            "Motif Balance is the first inverse design of regulatory DNA. Prior work exists.",
            "prior-art.first-pwm-inverse-design",
        ),
        (
            "The claim should be narrowed; the method achieved balanced binding affinity.",
            "biology.uncalibrated-affinity-or-outcome",
        ),
    ],
)
def test_claim_check_does_not_leak_suppression_across_clauses(text: str, rule_id: str) -> None:
    assert _rule_ids(text) == (rule_id,)


def test_claim_check_keeps_genuine_prior_art_and_meta_discussion_clean() -> None:
    text = (
        "Prior work by Martinez established PWM-informed inverse design, so the claim that this "
        "is the first inverse design of regulatory DNA is too broad."
    )

    assert check_claim_text(text) == ()


@pytest.mark.parametrize(
    "text",
    [
        "Motif Balance does not require training data and predicts binding.",
        "Do not claim the method is new and Motif Balance predicts binding.",
        "Unlike an affinity-calibrated comparator, Motif Balance predicts binding.",
        "A model-defined score shows that the TFs co-bind.",
        "A model-defined score shows that motifs can be superimposed.",
    ],
)
def test_claim_check_requires_match_specific_biological_qualification(text: str) -> None:
    assert _rule_ids(text) in {
        ("biology.uncalibrated-affinity-or-outcome",),
        ("biology.physical-superposition",),
    }


@pytest.mark.parametrize(
    "text",
    [
        "Motif Balance accepts binding-specificity models.",
        "Motif Balance uses supplied binding-specificity models.",
        "Motif Balance reports binding scores under the supplied PWM.",
    ],
)
def test_product_name_is_not_mistaken_for_the_verb_balance(text: str) -> None:
    assert check_claim_text(text) == ()


def test_balance_as_a_real_verb_remains_checked() -> None:
    assert _rule_ids("The method balances binding affinity.") == (
        "biology.uncalibrated-affinity-or-outcome",
    )


@pytest.mark.parametrize(
    "text",
    [
        "This claim is too broad if framed as the first inverse design of regulatory DNA.",
        "We do not claim that these model-defined sequence hypotheses predict binding.",
    ],
)
def test_common_match_adjacent_nonclaims_are_clean(text: str) -> None:
    assert check_claim_text(text) == ()


@pytest.mark.parametrize(
    "text",
    [
        "Whereas MATCH scans existing DNA, Motif Balance is the first inverse design of DNA.",
        "In contrast to prior work, Motif Balance is the first inverse design of DNA.",
        "MATCH is only a scanner and Motif Balance is the first inverse design of DNA.",
    ],
)
def test_prior_art_mentions_do_not_suppress_novelty_contrasts(text: str) -> None:
    assert _rule_ids(text) == ("prior-art.first-pwm-inverse-design",)


@pytest.mark.parametrize(
    "text",
    [
        "Exhaustive analysis of a finite benchmark found the optimal candidate.",
        "Exhaustive enumeration of a finite sample proves global optimality.",
    ],
)
def test_optimality_requires_complete_sequence_space_evidence(text: str) -> None:
    assert _rule_ids(text) == ("search.global-optimality",)


@pytest.mark.parametrize(
    "text",
    [
        "Exhaustive enumeration of the complete sequence space found the optimal candidate.",
        "We exhaustively enumerated all possible sequences and proved global optimality.",
        "Exhaustive enumeration of the entire DNA sequence space certified the optimal design.",
    ],
)
def test_explicit_complete_sequence_space_exactness_is_clean(text: str) -> None:
    assert check_claim_text(text) == ()


def test_calibrated_claimant_can_support_its_own_binding_interpretation() -> None:
    assert check_claim_text("An affinity-calibrated model predicts binding.") == ()


def test_adjacent_model_defined_qualifier_can_bound_superposition_language() -> None:
    assert check_claim_text("Model-defined motifs can be superimposed.") == ()


def test_claim_check_covers_supplied_reference_variants() -> None:
    text = """This is the first method for inverse design of DNA using PWMs.
We introduce a novel relative PWM score scale.
The study establishes motif \u201cmixability\u201d.
The study establishes motif superposability.
The study establishes capacities for superposition.
"""

    assert _rule_ids(text) == (
        "prior-art.first-pwm-inverse-design",
        "prior-art.novel-normalization",
        "biology.physical-superposition",
        "biology.physical-superposition",
        "biology.physical-superposition",
    )


def test_clause_spans_are_precomputed_once_for_many_same_line_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    context_sizes: list[int] = []
    original = claim_language._clause_spans
    original_context = claim_language._context_for_match

    def counted(line: str) -> tuple[claim_language._ClauseSpan, ...]:
        nonlocal calls
        calls += 1
        return original(line)

    def measured_context(
        line: str,
        spans: tuple[claim_language._ClauseSpan, ...],
        starts: tuple[int, ...],
        match: Match[str],
    ) -> tuple[str, int, int]:
        result = original_context(line, spans, starts, match)
        context_sizes.append(len(result[0]))
        return result

    monkeypatch.setattr(claim_language, "_clause_spans", counted)
    monkeypatch.setattr(claim_language, "_context_for_match", measured_context)
    text = "prefix " * 4096 + " and ".join("the search converged" for _ in range(256))

    assert len(check_claim_text(text)) == 256
    assert calls == 1
    assert context_sizes
    assert max(context_sizes) <= 512 + len("the search converged")


def test_claim_check_is_line_stable_deterministic_and_advisory_only() -> None:
    text = "The search converged.\nThe search converged."

    first = check_claim_text(text)

    assert first == check_claim_text(text)
    assert tuple(finding.line for finding in first) == (1, 2)
    assert tuple(finding.severity for finding in first) == ("warning", "warning")
    assert claim_language.__all__ == ("ClaimFinding", "check_claim_text")
    namespace: dict[str, object] = {}
    exec("from motif_balance.claim_language import *", {}, namespace)
    assert {name for name in namespace if not name.startswith("__")} == {
        "ClaimFinding",
        "check_claim_text",
    }
    assert "check_claim_text" not in motif_balance.__all__
    assert "ClaimFinding" not in motif_balance.__all__
