"""Deterministic advisory checks for wording used around Motif Balance results.

This module detects a bounded set of known publication hazards.  It does not
assess evidence, accept claims, search literature, or rewrite supplied text.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from re import Match, Pattern
from typing import Literal

__all__ = ("ClaimFinding", "check_claim_text")

ClaimSeverity = Literal["warning", "error"]


@dataclass(frozen=True, slots=True)
class ClaimFinding:
    """One source-located advisory finding."""

    rule_id: str
    severity: ClaimSeverity
    line: int
    matched_text: str
    rationale: str
    safer_wording: str


@dataclass(frozen=True, slots=True)
class _Rule:
    rule_id: str
    severity: ClaimSeverity
    pattern: Pattern[str]
    rationale: str
    safer_wording: str
    exception: Literal["none", "single-site", "exact", "calibrated", "model-defined"] = "none"


@dataclass(frozen=True, slots=True)
class _ClauseSpan:
    start: int
    end: int


def _pattern(expression: str) -> Pattern[str]:
    return re.compile(expression, re.IGNORECASE)


_RULES = (
    _Rule(
        "prior-art.first-pwm-inverse-design",
        "warning",
        _pattern(
            r"\bfirst\s+(?:"
            r"PWM[- ]based\s+inverse[- ]design|"
            r"method\s+for\s+inverse[- ]design\s+of\s+(?:regulatory\s+)?DNA"
            r"\s+(?:from|based\s+on|using)\s+(?:PWMs?|motif\s+models?)|"
            r"inverse[- ]design\s+(?:of\s+)?(?:regulatory\s+)?DNA|"
            r"inverse[- ]design(?:\s+[A-Za-z]+){0,8}?\s+"
            r"(?:from|based\s+on|using)\s+(?:PWMs?|motif\s+models?))\b"
        ),
        "PWM-informed inverse regulatory-DNA design predates Motif Balance.",
        "Describe the specific max-min, placement-free motif-compression problem implemented here.",
    ),
    _Rule(
        "prior-art.first-multiple-tfbs-design",
        "warning",
        _pattern(
            r"\bfirst\s+(?:multiple[- ]TFBS\s+design|"
            r"(?:[A-Za-z-]+\s+){0,5}to\s+(?:de\s+novo\s+)?design"
            r"(?:\s+[A-Za-z-]+){0,6}\s+multiple\s+TFBSs?)\b"
        ),
        "Prior tools and experimental work have designed sequences containing multiple TFBSs.",
        "State that site words, placements, strands, and overlaps are not prescribed in advance.",
    ),
    _Rule(
        "prior-art.first-motif-generator",
        "warning",
        _pattern(r"\bfirst\s+motif[- ]generating\s+(?:method|software|tool)\b"),
        "Existing software already generates sequences containing supplied motifs.",
        "Describe Motif Balance as a max-min inverse-design tool for explicit motif models.",
    ),
    _Rule(
        "prior-art.novel-normalization",
        "warning",
        _pattern(
            r"\b(?:novel|new|first)\s+(?:(?:motif[- ]score\s+)?normalization|"
            r"relative\s+PWM\s+score\s+scale)\b"
        ),
        "Motif-relative matrix-score normalization has established prior art, including MATCH.",
        "Treat relative PWM attainment as a declared scoring convention used by the objective.",
    ),
    _Rule(
        "semantics.single-site-range",
        "warning",
        _pattern(
            r"\b(?:attainable|theoretical)(?:\s+(?:motif|score|PWM|min[- ]to[- ]max)){0,2}"
            r"\s+range\b"
        ),
        "The implemented endpoints are extrema for one motif-width word; after a best-window scan, "
        "the lower endpoint need not be attainable by a full sequence.",
        "Say 'theoretical single-site log-likelihood-ratio range'.",
        "single-site",
    ),
    _Rule(
        "search.global-optimality",
        "warning",
        _pattern(
            r"\b(?:globally\s+optimal|global\s+optimum|the\s+optimal\s+sequence|"
            r"(?:the\s+)?optimal\s+(?:design|candidate|portfolio)s?|"
            r"(?:prove[sd]?|certif(?:y|ies|ied))\s+(?:global\s+)?optimality)\b"
        ),
        "Bounded annealed search reports the best result observed; it does not certify a global "
        "optimum.",
        "Use 'best observed under the declared evaluator-call budget' unless the space was "
        "exhaustively enumerated.",
        "exact",
    ),
    _Rule(
        "search.convergence",
        "warning",
        _pattern(
            r"\b(?:the\s+(?:search|optimizer|method)\s+)?(?:has\s+)?converged\b|"
            r"\b(?:demonstrates?|establishes?|proves?|reached?)\s+convergence\b"
        ),
        "Evaluator-budget exhaustion is not a convergence certificate.",
        "Report the stop reason and the running best-observed score over evaluator calls.",
    ),
    _Rule(
        "biology.uncalibrated-affinity-or-outcome",
        "warning",
        _pattern(
            r"\b(?:balanced|equal|strong|high|improved?|increased?|decreased?)\s+"
            r"(?:binding\s+affinit(?:y|ies)|binding(?![- ]specificity)|occupancy|expression)\b|"
            r"\b(?:predicts?|demonstrates?|establishes?|ensures?|achieves?|maximi[sz]es?|"
            r"(?<!Motif )balances?)\s+(?:[A-Za-z-]+\s+){0,3}"
            r"(?:binding\s+affinit(?:y|ies)|binding(?![- ]specificity)|occupancy|expression)\b"
        ),
        "PWM log-odds and relative attainment are not calibrated measurements or predictions of "
        "binding, occupancy, or expression.",
        "Describe model-relative motif scores, unless an independently calibrated model and "
        "supporting evidence justify the biological quantity.",
        "calibrated",
    ),
    _Rule(
        "biology.physical-superposition",
        "warning",
        _pattern(
            r"\bmotifs?\s+(?:are\s+|can\s+be\s+)?(?:physically\s+)?"
            r"(?:superimposed|mixable)(?:[^.;]{0,40}\bco-bind)?|"
            r"\bmotif\s+[\"'\u201c\u201d\u2018\u2019*]*"
            r"(?:superposition|mixability|superposability)"
            r"[\"'\u201c\u201d\u2018\u2019*]*|"
            r"\bcapacit(?:y|ies)\s+for\s+superposition\b|"
            r"\b(?:TFs?|motifs?)\s+(?:co-bind|co-occupy)\b"
        ),
        "Overlapping model-selected windows do not establish physical co-binding or occupancy.",
        "Describe model-defined shared coordinates or a named sequence-score compatibility "
        "descriptor.",
        "model-defined",
    ),
)

_IMMEDIATE_NEGATION = _pattern(
    r"(?:\b(?:does|do|did|is|are|was|were|has|have|had|can|cannot|must|should|would)"
    r"\s+not(?:\s+(?:the|a|an))?|\bnot\s+evidence\s+of)\s*$|"
    r"\b(?:does|do|did|can|cannot|must|should|would)\s+not\s+"
    r"(?:claim|establish|prove|demonstrate|show|certify|imply)\s+(?:that\s+)?$"
)
_CLAIM_REVIEW_PREFIX = _pattern(
    r"(?:\b(?:do|should|must|would)\s+not\s+claim|\bwithout\s+claiming)"
    r"(?:\s+(?!(?:and|but|yet|however|whereas|while)\b)[A-Za-z-]+){0,8}\s*$|"
    r"\bavoid(?:s|ed|ing)?\s+(?:the\s+)?(?:claim|wording|phrase)\s*$"
)
_META_REVIEW_PREFIX = _pattern(
    r"\b(?:this|the)\s+claim\s+is\s+too\s+broad\s+if\s+framed\s+as\s+(?:the\s+)?$"
)
_META_REVIEW_LANGUAGE = _pattern(
    r"\b(?:is|are)\s+(?:too\s+broad|unsupported|not\s+supported)|"
    r"\btoo\s+broad\s+if\s+framed\s+as\b|"
    r"\bmake(?:s)?\s+(?:that|this)\s+too\s+broad\b|"
    r"\bcreates?\s+an\s+opening\b|"
    r"\bthis\s+overstates\b|"
    r"\b(?:wording|claim|phrase)\s+(?:is|should\s+be)\s+(?:avoided|narrowed|rejected)\b"
)
_PRIOR_ART_REPORTING = _pattern(
    r"\b(?:prior\s+(?:art|work)|earlier\s+work|previous\s+work|Martinez|Barr|DeepTFBU|"
    r"MATCH|inMOTIFin)\b[^.;!?]{0,100}\b"
    r"(?:reported|described|called|claimed|characterized|identified)\b[^.;!?]{0,80}$"
)
_EXACT_ENUMERATION = _pattern(
    r"\b(?:exhaustive\s+enumeration|enumerat(?:e|ed|ion)\s+exhaustive(?:ly)?|"
    r"exhaustive(?:ly)?\s+enumerat(?:e|ed|ion))\b"
)
_COMPLETE_SEQUENCE_SPACE = _pattern(
    r"\b(?:(?:complete|entire)\s+(?:DNA\s+)?sequence\s+space|"
    r"all\s+(?:possible\s+)?sequences)\b"
)
_SINGLE_SITE_CONTEXT = _pattern(r"\b(?:single[- ]site|motif[- ]width\s+word|word[- ]level)\b")
_CALIBRATED_CLAIMANT = _pattern(
    r"(?:\b(?:an?|the|this|our)\s+(?:affinity|binding|activity)[- ]calibrated\s+"
    r"(?:model|predictor)|\b(?:model|predictor)\s+is\s+"
    r"(?:affinity|binding|activity)[- ]calibrated)\s+(?:and\s+)?$"
)
_MODEL_DEFINED_QUALIFIER = _pattern(
    r"\b(?:model[- ]defined|score[- ]defined|sequence[- ]score|sequence[- ]coordinate|"
    r"operationally\s+defined)\s+(?:motif\s+)?$"
)


_CLAUSE_BOUNDARY = _pattern(r"[;]|(?<!\d)[.!?](?!\d)|\b(?:but|however|yet)\b")
_CONTEXT_RADIUS = 256


def _clause_spans(line: str) -> tuple[_ClauseSpan, ...]:
    spans: list[_ClauseSpan] = []
    start = 0
    for boundary in _CLAUSE_BOUNDARY.finditer(line):
        spans.append(_ClauseSpan(start=start, end=boundary.start()))
        start = boundary.end()
    spans.append(_ClauseSpan(start=start, end=len(line)))
    return tuple(spans)


def _context_for_match(
    line: str,
    spans: tuple[_ClauseSpan, ...],
    starts: tuple[int, ...],
    match: Match[str],
) -> tuple[str, int, int]:
    index = max(0, bisect_right(starts, match.start()) - 1)
    span = spans[index]
    context_start = max(span.start, match.start() - _CONTEXT_RADIUS)
    context_end = min(span.end, match.end() + _CONTEXT_RADIUS)
    return (
        line[context_start:context_end],
        match.start() - context_start,
        match.end() - context_start,
    )


def _is_discussion_or_boundary(clause: str, match_start: int, match_end: int) -> bool:
    prefix = clause[:match_start]
    if (
        _IMMEDIATE_NEGATION.search(prefix)
        or _CLAIM_REVIEW_PREFIX.search(prefix)
        or _META_REVIEW_PREFIX.search(prefix)
    ):
        return True
    suffix = clause[match_end:]
    stripped_suffix = suffix.lstrip(" \t\"'\u201c\u201d\u2018\u2019*),:-")
    if len(suffix) - len(stripped_suffix) <= 16 and _META_REVIEW_LANGUAGE.match(stripped_suffix):
        return True
    return bool(_PRIOR_ART_REPORTING.search(prefix))


def _has_exception(rule: _Rule, clause: str, match: Match[str], match_start: int) -> bool:
    if rule.exception == "single-site":
        return bool(_SINGLE_SITE_CONTEXT.search(clause))
    if rule.exception == "exact":
        return bool(_EXACT_ENUMERATION.search(clause) and _COMPLETE_SEQUENCE_SPACE.search(clause))
    if rule.exception == "calibrated":
        return bool(_CALIBRATED_CLAIMANT.search(clause[:match_start]))
    if rule.exception == "model-defined":
        if re.search(r"\b(?:co-bind|co-occupy)\b", match.group(0), re.IGNORECASE):
            return False
        return bool(_MODEL_DEFINED_QUALIFIER.search(clause[:match_start]))
    return False


def check_claim_text(text: str) -> tuple[ClaimFinding, ...]:
    """Return deterministic advisory findings for known claim-language hazards.

    An empty tuple means that no configured wording hazard was found.  It does
    not establish evidentiary support, literature completeness, or suitability
    of the text for publication.
    """

    findings: list[ClaimFinding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        spans = _clause_spans(line)
        starts = tuple(span.start for span in spans)
        for rule in _RULES:
            for match in rule.pattern.finditer(line):
                clause, match_start, match_end = _context_for_match(line, spans, starts, match)
                if _is_discussion_or_boundary(clause, match_start, match_end) or _has_exception(
                    rule, clause, match, match_start
                ):
                    continue
                findings.append(
                    ClaimFinding(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        line=line_number,
                        matched_text=match.group(0),
                        rationale=rule.rationale,
                        safer_wording=rule.safer_wording,
                    )
                )
    return tuple(findings)
