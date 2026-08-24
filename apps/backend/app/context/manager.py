import os
from typing import List, Dict, Any, Optional
from app.context.models import (
    ContextTier, FileContextItem, TaskContextBundle, TokenBudgetReport
)
from app.context.indexer import code_indexer
from app.context.compressor import context_compressor
from app.context.budget import token_budget_manager
from app.tools.policies import workspace_validator
from app.core.logging import logger

class IntelligentContextManager:
    """
    Intelligent Context Optimization Engine:
    - Analyzes task goal and symbol references.
    - Classifies files into ContextTiers (Tier 1 Critical, Tier 2 Supporting, Tier 3 Background).
    - Assembles the minimum sufficient context bundle.
    - Applies progressive compression and tracks token reduction metrics.
    """

    @classmethod
    def assemble_optimized_context(
        cls,
        task_id: str,
        user_goal: str,
        workspace_root: str,
        targeted_files: Optional[List[str]] = None,
        raw_error: Optional[str] = None
    ) -> TaskContextBundle:
        tier_1: List[FileContextItem] = []
        tier_2: List[FileContextItem] = []
        raw_token_estimate = 0
        optimized_token_estimate = 0

        # 1. Discover targeted or symbol-relevant files
        candidate_files = set(targeted_files or [])

        # If no specific files given, scan workspace and find relevant matches
        if not candidate_files and os.path.exists(workspace_root):
            words = [w.lower() for w in user_goal.split() if len(w) > 3]
            for root, _, filenames in os.walk(workspace_root):
                for fn in filenames:
                    if fn.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".json")):
                        rel_path = os.path.relpath(os.path.join(root, fn), workspace_root)
                        try:
                            workspace_validator.validate_workspace_path(workspace_root, rel_path)
                            if any(w in fn.lower() or w in rel_path.lower() for w in words):
                                candidate_files.add(rel_path)
                        except Exception:
                            pass

        # 2. Process each candidate into Context Tiers
        for rel_path in candidate_files:
            full_path = os.path.join(workspace_root, rel_path)
            if not os.path.isfile(full_path):
                continue

            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                raw_tokens = len(content.split())
                raw_token_estimate += raw_tokens
                symbols = code_indexer.index_file(workspace_root, rel_path)

                # Classify Tier
                is_primary = targeted_files and rel_path in targeted_files
                if is_primary or "test" not in rel_path.lower():
                    tier_item = FileContextItem(
                        file_path=rel_path,
                        tier=ContextTier.TIER_1_CRITICAL,
                        relevance_score=1.0,
                        content=content,
                        is_truncated=False,
                        symbols=symbols
                    )
                    tier_1.append(tier_item)
                    optimized_token_estimate += raw_tokens
                else:
                    # Supporting secondary tier
                    tier_item = FileContextItem(
                        file_path=rel_path,
                        tier=ContextTier.TIER_2_SUPPORTING,
                        relevance_score=0.7,
                        content=content[:2000],  # compact preview
                        is_truncated=len(content) > 2000,
                        symbols=symbols
                    )
                    tier_2.append(tier_item)
                    optimized_token_estimate += len(tier_item.content.split())

            except Exception as e:
                logger.error(f"Error reading context file {rel_path}: {e}")

        # 3. Compress errors if present
        compressed_errors = []
        if raw_error:
            compressed = context_compressor.compress_test_output(raw_error)
            compressed_errors.append(compressed)
            raw_token_estimate += len(raw_error.split())
            optimized_token_estimate += len(compressed.split())

        # 4. Record token budget
        token_budget_manager.record_task_budget(
            task_id=task_id,
            raw_context_tokens=raw_token_estimate,
            optimized_context_tokens=optimized_token_estimate
        )

        return TaskContextBundle(
            task_id=task_id,
            user_goal=user_goal,
            tier_1_files=tier_1,
            tier_2_files=tier_2,
            relevant_errors=compressed_errors,
            total_estimated_tokens=optimized_token_estimate
        )

context_manager = IntelligentContextManager()
