import pytest
from app.context.models import ContextTier
from app.context.indexer import code_indexer
from app.context.compressor import context_compressor
from app.context.budget import token_budget_manager
from app.context.manager import context_manager

def test_code_intelligence_indexer(tmp_path):
    py_file = tmp_path / "service.py"
    py_file.write_text("""
class AuthService:
    def login(self, username, password):
        return True

    def logout(self):
        pass
""")
    symbols = code_indexer.index_file(str(tmp_path), "service.py")
    assert len(symbols) >= 2
    sym_names = [s.name for s in symbols]
    assert "AuthService" in sym_names
    assert "login" in sym_names

def test_context_compressor_test_output():
    # 200 lines of noise with 1 failure
    noisy_lines = [f"test_case_{i} PASSED [ 1%]" for i in range(100)]
    noisy_lines.append("FAILED tests/test_auth.py::test_jwt - AssertionError: 401 != 200")
    noisy_lines.extend([f"test_case_{i} PASSED [ 99%]" for i in range(100, 200)])
    raw_log = "\n".join(noisy_lines)

    compressed = context_compressor.compress_test_output(raw_log, max_lines=40)
    assert len(compressed.splitlines()) <= 45
    assert "FAILED tests/test_auth.py::test_jwt" in compressed

def test_token_budget_manager_reduction():
    report = token_budget_manager.record_task_budget(
        task_id="budget_task_01",
        raw_context_tokens=10000,
        optimized_context_tokens=2500,
        tool_tokens=500
    )
    assert report.reduction_percentage == 75.0
    assert report.total_task_tokens == 3000

def test_intelligent_context_manager_assembly(tmp_path):
    auth_file = tmp_path / "auth.py"
    auth_file.write_text("def authenticate(): return True")

    bundle = context_manager.assemble_optimized_context(
        task_id="task_bundle_01",
        user_goal="Fix authenticate function in auth",
        workspace_root=str(tmp_path),
        targeted_files=["auth.py"],
        raw_error="FAILED auth_test.py::test_auth - AssertionError"
    )
    assert len(bundle.tier_1_files) == 1
    assert bundle.tier_1_files[0].file_path == "auth.py"
    assert len(bundle.relevant_errors) == 1
    assert bundle.total_estimated_tokens > 0
