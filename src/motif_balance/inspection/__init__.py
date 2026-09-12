"""Advanced review of verified results or replayed caller-supplied candidates."""

from .api import inspect_result
from .candidate_model import CandidateInspection
from .model import ResultInspection
from .supplied import inspect_candidate

__all__ = ["CandidateInspection", "ResultInspection", "inspect_candidate", "inspect_result"]
