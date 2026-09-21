"""Execute and verify a result together with its software and runtime record.

Maintainer(s): Eric J. South, Dunlop Lab
"""

from .workspace import execute_design_workspace, verify_execution_workspace

__all__ = ["execute_design_workspace", "verify_execution_workspace"]
