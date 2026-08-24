import re
from typing import List, Dict, Any

class ContextCompressor:
    """
    Intelligent Context and Tool Output Compressor:
    - Filters multi-thousand-line test logs down to failing tests, stack traces, and line numbers.
    - Strips noisy build stdout while preserving error codes and diagnostic messages.
    - Summarizes repetitive diffs and search results.
    """

    @classmethod
    def compress_test_output(cls, raw_output: str, max_lines: int = 40) -> str:
        """Compresses terminal test output (pytest, jest, etc.) to retain only failures."""
        if not raw_output:
            return ""

        lines = raw_output.splitlines()
        if len(lines) <= max_lines:
            return raw_output

        failing_sections = []
        is_capturing = False
        captured = []

        for line in lines:
            # Detect pytest / test failure headers
            if "FAILED " in line or "FAIL " in line or "ERROR " in line or "AssertionError" in line or "Traceback" in line:
                is_capturing = True

            if is_capturing:
                captured.append(line)
                if len(captured) >= 15:  # capture reasonable window per failure
                    failing_sections.extend(captured)
                    failing_sections.append("... [truncated noise] ...")
                    captured = []
                    is_capturing = False

        if captured:
            failing_sections.extend(captured)

        # If nothing specifically matched, return head + tail
        if not failing_sections:
            return "\n".join(lines[:15] + ["\n... [output compressed] ...\n"] + lines[-15:])

        return "\n".join(failing_sections[:max_lines])

    @classmethod
    def compress_git_diff(cls, diff: str, max_lines: int = 50) -> str:
        """Compresses unified diffs to focus on changed headers and content."""
        if not diff:
            return ""
        lines = diff.splitlines()
        if len(lines) <= max_lines:
            return diff

        return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} more diff lines omitted] ..."

context_compressor = ContextCompressor()
