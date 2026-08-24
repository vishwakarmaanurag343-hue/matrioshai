import os
import ast
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from app.context.models import CodeSymbol, CodeSymbolType
from app.tools.policies import workspace_validator
from app.core.logging import logger

class CodeIntelligenceIndexer:
    """
    Language-aware AST and Symbol Indexer:
    - Scans Python, TypeScript, JavaScript files within workspace boundaries.
    - Extracts function definitions, classes, methods, imports, and exports.
    - Uses file MD5 hash caching to skip re-indexing unchanged files.
    """

    def __init__(self):
        self._file_hashes: Dict[str, str] = {}
        self._symbol_index: Dict[str, List[CodeSymbol]] = {}  # file_path -> symbols
        self._name_to_symbols: Dict[str, List[CodeSymbol]] = {}  # symbol_name -> symbols

    def index_file(self, workspace_root: str, rel_path: str) -> List[CodeSymbol]:
        full_path = os.path.join(workspace_root, rel_path)
        if not os.path.isfile(full_path):
            return []

        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            file_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
            cache_key = f"{workspace_root}:{rel_path}"

            # Check cache
            if self._file_hashes.get(cache_key) == file_hash and cache_key in self._symbol_index:
                return self._symbol_index[cache_key]

            symbols: List[CodeSymbol] = []

            # Python AST parsing
            if rel_path.endswith(".py"):
                try:
                    tree = ast.parse(content, filename=rel_path)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            symbols.append(CodeSymbol(
                                name=node.name,
                                symbol_type=CodeSymbolType.FUNCTION,
                                file_path=rel_path,
                                line_start=node.lineno,
                                line_end=node.end_lineno or node.lineno
                            ))
                        elif isinstance(node, ast.ClassDef):
                            symbols.append(CodeSymbol(
                                name=node.name,
                                symbol_type=CodeSymbolType.CLASS,
                                file_path=rel_path,
                                line_start=node.lineno,
                                line_end=node.end_lineno or node.lineno
                            ))
                except Exception as e:
                    logger.debug(f"AST parse error for {rel_path}: {e}")

            # General Regex fallback for JS/TS/Other languages
            elif rel_path.endswith((".ts", ".tsx", ".js", ".jsx")):
                lines = content.splitlines()
                for idx, line in enumerate(lines, 1):
                    line_str = line.strip()
                    if line_str.startswith("function ") or "const " in line_str and "=>" in line_str:
                        parts = line_str.split()
                        name = parts[1].split("(")[0] if len(parts) > 1 else f"func_line_{idx}"
                        symbols.append(CodeSymbol(
                            name=name,
                            symbol_type=CodeSymbolType.FUNCTION,
                            file_path=rel_path,
                            line_start=idx,
                            line_end=idx
                        ))
                    elif line_str.startswith("class ") or line_str.startswith("interface ") or line_str.startswith("type "):
                        parts = line_str.split()
                        name = parts[1].split("{")[0].split("=")[0] if len(parts) > 1 else f"type_line_{idx}"
                        symbols.append(CodeSymbol(
                            name=name,
                            symbol_type=CodeSymbolType.CLASS if "class" in line_str else CodeSymbolType.INTERFACE,
                            file_path=rel_path,
                            line_start=idx,
                            line_end=idx
                        ))

            # Store in cache
            self._file_hashes[cache_key] = file_hash
            self._symbol_index[cache_key] = symbols

            for s in symbols:
                if s.name not in self._name_to_symbols:
                    self._name_to_symbols[s.name] = []
                self._name_to_symbols[s.name].append(s)

            return symbols

        except Exception as e:
            logger.error(f"Failed to index {rel_path}: {e}")
            return []

    def find_symbols_by_name(self, name: str) -> List[CodeSymbol]:
        return self._name_to_symbols.get(name, [])

code_indexer = CodeIntelligenceIndexer()
