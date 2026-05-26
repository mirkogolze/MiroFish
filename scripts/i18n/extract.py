#!/usr/bin/env python3
"""
Phase 1: Extract Chinese text segments from Python source files using tokenize.

Scans all backend Python files, identifies tokens containing Chinese characters,
classifies them by kind (comment, docstring, log_message, fstring_text, llm_prompt,
argparse_help, error_message), and writes a JSONL manifest with exact positions.

Usage:
    python scripts/i18n/extract.py [--output PATH] [--file PATH]
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import tokenize
from pathlib import Path

# Chinese character detection (CJK Unified Ideographs)
CJK_RE = re.compile(r'[\u4e00-\u9fff]')

# Placeholder patterns to extract from strings
PLACEHOLDER_PATTERNS = [
    re.compile(r'\{[^{}]*\}'),          # {var}, {var!r}, {var:fmt}, {var=}
    re.compile(r'%(?:\([^)]+\))?[sdifFeEgGxXocrba%]'),  # %s, %(name)s, %d
    re.compile(r'\$\{?[a-zA-Z_]\w*\}?'),  # $name, ${name}
]

# Protected technical terms (never translate)
PROTECTED_TERMS = [
    "LangChain", "Zep", "ReACT", "Agent", "Redis", "Celery", "Flask",
    "Python", "LLM", "API", "JSON", "YAML", "Docker", "OASIS", "MiroFish",
    "Miro", "GraphRAG", "OpenAI", "Anthropic", "GPT", "ReAct", "RAG",
    "FastAPI", "SQLite", "PostgreSQL", "MongoDB", "Pydantic", "async",
    "await", "Thread", "Process", "Celery", "RabbitMQ", "WebSocket",
    "HTTP", "REST", "CRUD", "UUID", "URL", "URI", "SSE", "OAuth",
    "JWT", "Bearer", "Token", "Markdown", "HTML", "CSS", "JS",
    "TypeScript", "Vue", "React", "Node", "npm", "pip", "uv",
    "git", "GitHub", "GitLab", "CI/CD", "pytest", "unittest",
    "loguru", "logger", "handler", "formatter", "config",
    "Twitter", "Reddit", "LinkedIn", "Facebook", "Instagram",
    "Simulation", "Ontology", "Entity", "Relationship",
]

# Files to skip (already translated or excluded)
SKIP_FILES = {
    "run_parallel_simulation.py",
    "run_twitter_simulation.py",
    "run_reddit_simulation.py",
    "oasis_profile_generator.py",
    "zep_graph_memory_updater.py",
}

# Backend directories to scan
SCAN_DIRS = [
    "backend/app",
    "backend/scripts",
    "backend/run.py",
]


def find_python_files(project_root: Path) -> list[Path]:
    """Find all Python files in backend directories."""
    files = []
    for scan_path in SCAN_DIRS:
        full_path = project_root / scan_path
        if full_path.is_file() and full_path.suffix == '.py':
            if full_path.name not in SKIP_FILES:
                files.append(full_path)
        elif full_path.is_dir():
            for py_file in sorted(full_path.rglob("*.py")):
                if py_file.name not in SKIP_FILES:
                    files.append(py_file)
    return sorted(set(files))


def extract_placeholders(text: str) -> list[str]:
    """Extract all placeholder patterns from a string."""
    placeholders = []
    for pattern in PLACEHOLDER_PATTERNS:
        placeholders.extend(pattern.findall(text))
    return sorted(set(placeholders))


def find_protected_terms(text: str) -> list[str]:
    """Find protected terms present in the text."""
    found = []
    for term in PROTECTED_TERMS:
        if term in text:
            found.append(term)
    return sorted(found)


def classify_token(tok_type: int, tok_string: str, tokens_context: list, idx: int) -> str:
    """
    Classify a token into a semantic kind.
    
    Returns one of: comment, docstring, log_message, error_message,
                    llm_prompt, fstring_text, argparse_help, string_constant
    """
    tok_type_name = tokenize.tok_name.get(tok_type, "")
    
    # Comments are straightforward
    if tok_type == tokenize.COMMENT:
        return "comment"
    
    # FSTRING_MIDDLE (Python 3.12+)
    if tok_type_name == "FSTRING_MIDDLE":
        return "fstring_text"
    
    # For STRING tokens, classify based on context
    if tok_type == tokenize.STRING:
        # Check if it's a docstring (triple-quoted, first statement in module/class/func)
        if tok_string.startswith(('"""', "'''", 'r"""', "r'''")):
            # Look at preceding tokens for def/class or module start
            # Simple heuristic: triple-quoted + longer than 1 line → likely docstring
            if '\n' in tok_string or len(tok_string) > 80:
                # Check for LLM prompt indicators
                if _is_llm_prompt(tok_string):
                    return "llm_prompt"
                return "docstring"
        
        # Check if it's an LLM prompt (multi-line with instruction markers)
        if _is_llm_prompt(tok_string):
            return "llm_prompt"
        
        # Check surrounding context for classification
        context_before = _get_context_before(tokens_context, idx)
        
        if context_before:
            # Log messages
            if re.search(r'logger\.(info|debug|warning|error|critical|exception)', context_before):
                return "log_message"
            if re.search(r'logging\.(info|debug|warning|error|critical)', context_before):
                return "log_message"
            if 'print(' in context_before:
                return "log_message"
            
            # Error messages
            if re.search(r'raise\s+\w+', context_before):
                return "error_message"
            if 'HTTPException' in context_before:
                return "error_message"
            
            # Argparse help
            if 'help=' in context_before or 'add_argument' in context_before:
                return "argparse_help"
            if 'description=' in context_before:
                return "argparse_help"
        
        return "string_constant"
    
    return "string_constant"


def _is_llm_prompt(text: str) -> bool:
    """Detect if a string is likely an LLM prompt."""
    indicators = ['你是', '请', '任务', '规则', '要求', '输出格式', '【', '】',
                  '步骤', '注意', '必须', '不要', '系统提示', 'system', 'prompt']
    # Need multiple indicators to be confident
    matches = sum(1 for ind in indicators if ind in text)
    return matches >= 3 and len(text) > 100


def _get_context_before(tokens: list, idx: int) -> str:
    """Get text context from preceding tokens on the same or previous line."""
    context_parts = []
    target_row = tokens[idx][2][0] if idx < len(tokens) else 0
    
    # Look back up to 5 tokens
    for i in range(max(0, idx - 5), idx):
        tok = tokens[i]
        if tok[2][0] >= target_row - 1:  # Same or previous line
            context_parts.append(tok[1])
    
    return ' '.join(context_parts)


def get_source_lines(content: str, start_row: int, end_row: int, context_n: int = 2) -> dict:
    """Get context lines around a segment."""
    lines = content.splitlines()
    
    # Context before (up to context_n lines before start)
    before_start = max(0, start_row - 1 - context_n)
    before_end = start_row - 1
    context_before = '\n'.join(lines[before_start:before_end]).strip()
    
    # Context after (up to context_n lines after end)
    after_start = end_row  # end_row is 1-based, so this is the line after
    after_end = min(len(lines), after_start + context_n)
    context_after = '\n'.join(lines[after_start:after_end]).strip()
    
    return {
        "context_before": context_before,
        "context_after": context_after,
    }


def extract_chinese_text(tok_string: str, tok_type: int) -> str:
    """
    Extract the translatable Chinese text content from a token.
    
    For comments: strip the '# ' prefix
    For strings: strip quotes and string prefix (f, r, b, etc.)
    """
    tok_type_name = tokenize.tok_name.get(tok_type, "")
    
    if tok_type == tokenize.COMMENT:
        # Remove '# ' prefix
        text = tok_string
        if text.startswith('#'):
            text = text[1:].lstrip()
        return text
    
    if tok_type_name == "FSTRING_MIDDLE":
        # FSTRING_MIDDLE is already the raw text content
        return tok_string
    
    if tok_type == tokenize.STRING:
        # Remove string prefix and quotes
        text = tok_string
        # Strip prefix (f, r, b, u, fr, rf, br, rb)
        prefix_match = re.match(r'^([fFrRbBuU]{0,2})(\'\'\'|"""|\'|")', text)
        if prefix_match:
            prefix = prefix_match.group(1)
            quote = prefix_match.group(2)
            text = text[len(prefix) + len(quote):]
            # Remove trailing quote
            if text.endswith(quote):
                text = text[:-len(quote)]
        return text
    
    return tok_string


def get_string_metadata(tok_string: str, tok_type: int) -> dict:
    """Extract prefix and quote style from a string token."""
    tok_type_name = tokenize.tok_name.get(tok_type, "")
    
    if tok_type == tokenize.COMMENT:
        # Determine comment prefix (# or #! etc.)
        prefix = ""
        if tok_string.startswith('# '):
            prefix = "# "
        elif tok_string.startswith('#'):
            prefix = "#"
        return {"prefix": prefix, "quote_style": None}
    
    if tok_type_name == "FSTRING_MIDDLE":
        return {"prefix": "", "quote_style": None}
    
    if tok_type == tokenize.STRING:
        prefix_match = re.match(r'^([fFrRbBuU]{0,2})(\'\'\'|"""|\'|")', tok_string)
        if prefix_match:
            return {
                "prefix": prefix_match.group(1),
                "quote_style": prefix_match.group(2),
            }
    
    return {"prefix": "", "quote_style": None}


def make_segment_id(file_rel: str, start_row: int, start_col: int, tok_type_name: str) -> str:
    """Create a stable segment ID."""
    return f"{file_rel}:{start_row}:{start_col}:{tok_type_name}"


def process_file(file_path: Path, project_root: Path) -> list[dict]:
    """Process a single Python file and extract Chinese segments."""
    segments = []
    rel_path = str(file_path.relative_to(project_root))
    
    try:
        content = file_path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, IOError) as e:
        print(f"  SKIP {rel_path}: {e}", file=sys.stderr)
        return []
    
    # Tokenize
    try:
        tokens_list = list(tokenize.generate_tokens(io.StringIO(content).readline))
    except tokenize.TokenError as e:
        print(f"  TOKENIZE ERROR {rel_path}: {e}", file=sys.stderr)
        return []
    
    for idx, tok in enumerate(tokens_list):
        tok_type, tok_string, tok_start, tok_end, tok_line = tok
        tok_type_name = tokenize.tok_name.get(tok_type, "UNKNOWN")
        
        # Skip non-text tokens
        if tok_type not in (tokenize.COMMENT, tokenize.STRING) and tok_type_name != "FSTRING_MIDDLE":
            continue
        
        # Check for Chinese characters
        if not CJK_RE.search(tok_string):
            continue
        
        start_row, start_col = tok_start
        end_row, end_col = tok_end
        
        # Classify
        kind = classify_token(tok_type, tok_string, tokens_list, idx)
        
        # Extract translatable text
        source_text = extract_chinese_text(tok_string, tok_type)
        
        # Get metadata
        metadata = get_string_metadata(tok_string, tok_type)
        
        # Get context
        context = get_source_lines(content, start_row, end_row)
        
        # Extract placeholders and protected terms
        placeholders = extract_placeholders(source_text)
        protected = find_protected_terms(source_text)
        
        # Build segment
        segment_id = make_segment_id(rel_path, start_row, start_col, tok_type_name)
        
        segment = {
            "id": segment_id,
            "file": rel_path,
            "token_type": tok_type_name,
            "kind": kind,
            "start_row": start_row,
            "start_col": start_col,
            "end_row": end_row,
            "end_col": end_col,
            "source_text": source_text,
            "full_token_text": tok_string,
            "prefix": metadata["prefix"],
            "quote_style": metadata["quote_style"],
            "context_before": context["context_before"],
            "context_after": context["context_after"],
            "placeholders": placeholders,
            "protected_terms": protected,
        }
        
        segments.append(segment)
    
    return segments


def main():
    parser = argparse.ArgumentParser(description="Extract Chinese text segments from Python files")
    parser.add_argument("--output", "-o", default="scripts/i18n/output/segments.jsonl",
                        help="Output JSONL file path (default: scripts/i18n/output/segments.jsonl)")
    parser.add_argument("--file", "-f", help="Process a single file instead of all backend files")
    parser.add_argument("--stats", action="store_true", help="Print statistics after extraction")
    args = parser.parse_args()
    
    # Find project root (where this script's parent's parent is)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent  # scripts/i18n/ → scripts/ → project root
    
    # Determine files to process
    if args.file:
        target = project_root / args.file
        if not target.exists():
            print(f"ERROR: File not found: {target}", file=sys.stderr)
            sys.exit(1)
        files = [target]
    else:
        files = find_python_files(project_root)
    
    print(f"Scanning {len(files)} Python files...")
    
    # Process all files
    all_segments = []
    for f in files:
        rel = str(f.relative_to(project_root))
        segments = process_file(f, project_root)
        if segments:
            print(f"  {rel}: {len(segments)} segments")
            all_segments.extend(segments)
    
    # Write output
    output_path = project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as fp:
        for seg in all_segments:
            fp.write(json.dumps(seg, ensure_ascii=False) + '\n')
    
    print(f"\nTotal: {len(all_segments)} segments → {output_path}")
    
    # Statistics
    if args.stats or not args.file:
        kinds = {}
        files_count = {}
        for seg in all_segments:
            kinds[seg["kind"]] = kinds.get(seg["kind"], 0) + 1
            files_count[seg["file"]] = files_count.get(seg["file"], 0) + 1
        
        print("\nBy kind:")
        for kind, count in sorted(kinds.items(), key=lambda x: -x[1]):
            print(f"  {kind}: {count}")
        
        print("\nBy file (top 10):")
        for f, count in sorted(files_count.items(), key=lambda x: -x[1])[:10]:
            print(f"  {f}: {count}")
        
        # Dedup stats
        unique_texts = set(seg["source_text"] for seg in all_segments)
        print(f"\nUnique source texts: {len(unique_texts)} (of {len(all_segments)} total)")


if __name__ == "__main__":
    main()
