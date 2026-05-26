#!/usr/bin/env python3
"""
Phase 5: Patch source files with validated translations.

Applies accepted translations to the original Python files using
reverse-positional Unicode splice. Validates each patched file with
py_compile and ast.parse.

Usage:
    python scripts/i18n/patch.py [--input PATH] [--segments PATH] [--dry-run]
"""
import argparse
import ast
import json
import os
import py_compile
import re
import sys
import tempfile
from pathlib import Path
from collections import defaultdict

# CJK detection for post-patch check
CJK_RE = re.compile(r'[\u4e00-\u9fff]')


def load_validated_translations(input_path: Path) -> list[dict]:
    """Load validated translations (only accepted ones)."""
    translations = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                entry = json.loads(line)
                # Accept all translations that have content (keine Ausnahmen)
                if entry.get("translation", "").strip():
                    translations.append(entry)
    return translations


def load_segments_index(segments_path: Path) -> dict[str, dict]:
    """Load segments indexed by ID for position/metadata lookup."""
    index = {}
    with open(segments_path, 'r', encoding='utf-8') as f:
        for line in f:
            seg = json.loads(line.strip())
            index[seg["id"]] = seg
    return index


def load_dedup_index(dedup_path: Path) -> dict[str, list[str]]:
    """Load dedup index to propagate translations to duplicates."""
    if not dedup_path.exists():
        return {}
    with open(dedup_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_replacement(segment: dict, translation: str) -> str:
    """
    Build the full replacement token text from a translation.
    Preserves prefix, quote style, etc.
    """
    token_type = segment["token_type"]
    
    if token_type == "COMMENT":
        prefix = segment.get("prefix", "# ")
        return f"{prefix}{translation}"
    
    if token_type == "FSTRING_MIDDLE":
        # FSTRING_MIDDLE: return as-is. The tokenizer positions account for
        # one brace of each {{/}} pair; the other stays in the gap.
        return translation
    
    if token_type == "STRING":
        prefix = segment.get("prefix", "")
        quote_style = segment.get("quote_style", '"')
        # Escape any unescaped quote characters introduced by translation
        escaped = translation.replace(quote_style, f'\\{quote_style}')
        return f"{prefix}{quote_style}{escaped}{quote_style}"
    
    # Fallback
    return translation


def apply_patches_to_file(file_path: Path, patches: list[dict]) -> str | None:
    """
    Apply patches to a file using reverse-positional Unicode splice.
    
    Returns the patched content, or None if no patches applied.
    """
    content = file_path.read_text(encoding='utf-8')
    lines = content.splitlines(keepends=True)
    
    # Sort patches by position DESCENDING (last first → offsets stay stable)
    patches_sorted = sorted(patches, key=lambda p: (p["end_row"], p["end_col"]), reverse=True)
    
    for patch in patches_sorted:
        start_row = patch["start_row"] - 1  # Convert to 0-based
        start_col = patch["start_col"]
        end_row = patch["end_row"] - 1
        end_col = patch["end_col"]
        replacement = patch["replacement"]
        
        # Handle single-line vs multi-line tokens
        if start_row == end_row:
            # Single line: simple splice
            line = lines[start_row]
            new_line = line[:start_col] + replacement + line[end_col:]
            lines[start_row] = new_line
        else:
            # Multi-line: replace from start to end across lines
            # Get prefix from first line (before token start)
            first_line_prefix = lines[start_row][:start_col]
            # Get suffix from last line (after token end)
            last_line_suffix = lines[end_row][end_col:]
            
            # Build new content for this range
            new_content = first_line_prefix + replacement + last_line_suffix
            
            # Replace lines[start_row:end_row+1] with new content
            lines[start_row:end_row + 1] = [new_content]
    
    return ''.join(lines)


def validate_patched_content(content: str, file_path: Path) -> list[str]:
    """
    Validate patched file content.
    Returns list of error messages (empty = valid).
    """
    errors = []
    
    # 1. Syntax check via compile
    try:
        compile(content, str(file_path), 'exec')
    except SyntaxError as e:
        errors.append(f"SyntaxError: {e.msg} (line {e.lineno})")
    
    # 2. AST parse
    try:
        ast.parse(content)
    except SyntaxError as e:
        if not errors:  # Don't duplicate
            errors.append(f"AST parse error: {e.msg} (line {e.lineno})")
    
    return errors


def main():
    parser = argparse.ArgumentParser(description="Patch source files with validated translations")
    parser.add_argument("--input", "-i", default="scripts/i18n/output/translations_validated.jsonl",
                        help="Validated translations JSONL")
    parser.add_argument("--segments", "-s", default="scripts/i18n/output/segments.jsonl",
                        help="Original segments JSONL")
    parser.add_argument("--dedup", default="scripts/i18n/output/dedup_index.json",
                        help="Dedup index JSON")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show changes without writing files")
    parser.add_argument("--file", "-f", help="Patch only a specific file")
    args = parser.parse_args()
    
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent
    
    input_path = project_root / args.input
    segments_path = project_root / args.segments
    dedup_path = project_root / args.dedup
    
    if not input_path.exists():
        print(f"ERROR: Validated translations not found: {input_path}", file=sys.stderr)
        print("Run validate.py first.", file=sys.stderr)
        sys.exit(1)
    
    # Load data
    translations = load_validated_translations(input_path)
    segments_index = load_segments_index(segments_path)
    dedup_index = load_dedup_index(dedup_path)
    
    print(f"Loaded {len(translations)} accepted translations")
    
    # Build translation lookup: source_text → translation
    translation_lookup = {}
    for t in translations:
        translation_lookup[t["source_text"].strip()] = t["translation"]
    
    # Build patches per file (including duplicates via dedup index)
    patches_by_file = defaultdict(list)
    
    # First: direct translations (segments that were translated)
    translated_ids = {t["id"] for t in translations}
    
    for t in translations:
        seg = segments_index.get(t["id"])
        if not seg:
            continue
        
        replacement = build_replacement(seg, t["translation"])
        patch = {
            "id": seg["id"],
            "start_row": seg["start_row"],
            "start_col": seg["start_col"],
            "end_row": seg["end_row"],
            "end_col": seg["end_col"],
            "replacement": replacement,
            "source_text": seg["source_text"],
            "translation": t["translation"],
        }
        patches_by_file[seg["file"]].append(patch)
    
    # Second: propagate translations to duplicates
    propagated = 0
    for source_text, seg_ids in dedup_index.items():
        # Find translation for this source text
        translation = translation_lookup.get(source_text.strip())
        if not translation:
            continue
        
        for seg_id in seg_ids:
            if seg_id in translated_ids:
                continue  # Already handled above
            
            seg = segments_index.get(seg_id)
            if not seg:
                continue
            
            replacement = build_replacement(seg, translation)
            patch = {
                "id": seg["id"],
                "start_row": seg["start_row"],
                "start_col": seg["start_col"],
                "end_row": seg["end_row"],
                "end_col": seg["end_col"],
                "replacement": replacement,
                "source_text": seg["source_text"],
                "translation": translation,
            }
            patches_by_file[seg["file"]].append(patch)
            propagated += 1
    
    print(f"Propagated {propagated} duplicate translations")
    total_patches = sum(len(p) for p in patches_by_file.values())
    print(f"Total patches to apply: {total_patches} across {len(patches_by_file)} files")
    
    if args.file:
        # Filter to single file
        target = args.file
        patches_by_file = {k: v for k, v in patches_by_file.items() if k == target}
        if not patches_by_file:
            print(f"No patches for file: {target}")
            sys.exit(0)
    
    # Apply patches per file
    results = {"success": 0, "failed": 0, "skipped": 0}
    failed_files = []
    
    for rel_path, patches in sorted(patches_by_file.items()):
        file_path = project_root / rel_path
        
        if not file_path.exists():
            print(f"  SKIP {rel_path}: file not found")
            results["skipped"] += 1
            continue
        
        # Apply patches
        patched_content = apply_patches_to_file(file_path, patches)
        
        if patched_content is None:
            results["skipped"] += 1
            continue
        
        # Validate
        errors = validate_patched_content(patched_content, file_path)
        
        if errors:
            print(f"  FAIL {rel_path}: {errors[0]}")
            failed_files.append({"file": rel_path, "errors": errors, "patches": len(patches)})
            results["failed"] += 1
            continue
        
        # Check remaining CJK
        remaining_cjk = len(CJK_RE.findall(patched_content))
        
        if args.dry_run:
            print(f"  [DRY RUN] {rel_path}: {len(patches)} patches, {remaining_cjk} CJK remaining")
        else:
            # Write patched file
            file_path.write_text(patched_content, encoding='utf-8')
            print(f"  ✓ {rel_path}: {len(patches)} patches applied, {remaining_cjk} CJK remaining")
        
        results["success"] += 1
    
    # Summary
    print(f"\n{'=' * 40}")
    print(f"Success: {results['success']} files")
    print(f"Failed:  {results['failed']} files")
    print(f"Skipped: {results['skipped']} files")
    
    if failed_files:
        print(f"\nFailed files:")
        for ff in failed_files:
            print(f"  {ff['file']}: {ff['errors'][0]}")
    
    # Write patch report
    report_path = project_root / "scripts/i18n/output/patch_report.json"
    report = {
        "results": results,
        "failed_files": failed_files,
        "total_patches": total_patches,
        "files_patched": list(patches_by_file.keys()),
    }
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
