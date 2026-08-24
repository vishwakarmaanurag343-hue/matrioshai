# MATRIOSHAI Required Fixes & Recommendations

## Priority 0 (System Blockers):
- **None**: All systems operational, zero test failures, zero typecheck errors.

## Priority 1 (Critical Production Enhancements):
- **None**: All security boundaries and transaction controls fail closed as required.

## Priority 2 (Operational Recommendations):
1. **Persistent Checkpoint Database**:
   - Enhance in-memory `WorkflowCheckpoint` and `TransactionSnapshot` stores with optional SQLite WAL disk persistence across power loss events.
2. **External Model Provider API Keys**:
   - Ensure production container environments supply valid API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`) for live model completions.
