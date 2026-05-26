#!/usr/bin/env python3
"""
Phase 4: Validate translations before patching.

Checks each translation against hard rules (placeholders, protected terms, CJK residue)
and computes a quality score. Outputs validated JSONL + review report.

Usage:
    python scripts/i18n/validate.py [--input PATH] [--segments PATH] [--output PATH]
"""
import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

# CJK detection
CJK_RE = re.compile(r'[\u4e00-\u9fff]')

# Placeholder patterns (same as extract.py)
PLACEHOLDER_PATTERNS = [
    re.compile(r'\{[^{}]*\}'),
    re.compile(r'%(?:\([^)]+\))?[sdifFeEgGxXocrba%]'),
]


def extract_placeholders(text: str) -> set[str]:
    """Extract placeholder patterns from text."""
    found = set()
    for pattern in PLACEHOLDER_PATTERNS:
        found.update(pattern.findall(text))
    return found


def validate_entry(entry: dict, segment: dict | None) -> dict:
    """
    Validate a single translation entry.
    Returns the entry with added 'score', 'status', and 'flags' fields.
    """
    translation = entry.get("translation", "")
    source_text = entry.get("source_text", "")
    flags = []
    score = 100
    hard_fail = False
    
    # === Hard Blockers ===
    
    # 1. Empty translation
    if not translation or not translation.strip():
        flags.append("EMPTY_TRANSLATION")
        hard_fail = True
    
    # 2. Placeholder integrity
    source_ph = extract_placeholders(source_text)
    trans_ph = extract_placeholders(translation) if translation else set()
    
    missing_ph = source_ph - trans_ph
    extra_ph = trans_ph - source_ph
    
    if missing_ph:
        flags.append(f"MISSING_PLACEHOLDERS: {missing_ph}")
        hard_fail = True
    if extra_ph:
        flags.append(f"EXTRA_PLACEHOLDERS: {extra_ph}")
        score -= 30
    
    # 3. Protected terms changed
    if segment and segment.get("protected_terms"):
        for term in segment["protected_terms"]:
            if term in source_text and term not in translation and translation:
                # Term was in source and should be in translation too
                # But only flag if it's a standalone term, not part of a larger word
                if re.search(r'\b' + re.escape(term) + r'\b', source_text):
                    flags.append(f"PROTECTED_TERM_MISSING: {term}")
                    score -= 15
    
    # 4. CJK residue in translation
    if translation and CJK_RE.search(translation):
        cjk_chars = CJK_RE.findall(translation)
        if len(cjk_chars) > 2:  # Allow very few (might be intentional like 「」)
            flags.append(f"CJK_RESIDUE: {''.join(cjk_chars[:10])}")
            score -= 40
    
    # 5. Translation identical to source
    if translation and translation.strip() == source_text.strip():
        flags.append("IDENTICAL_TO_SOURCE")
        score -= 40
    
    # === Soft Checks (score deductions) ===
    
    if translation and not hard_fail:
        # Length ratio check
        src_len = len(source_text.strip())
        trans_len = len(translation.strip())
        if src_len > 0:
            ratio = trans_len / src_len
            if ratio < 0.2:
                flags.append(f"TOO_SHORT: ratio={ratio:.2f}")
                score -= 15
            elif ratio > 5.0:
                flags.append(f"TOO_LONG: ratio={ratio:.2f}")
                score -= 15
        
        # Contains markdown artifacts
        if re.search(r'^```|^#+\s|^\*\*|^---', translation, re.MULTILINE):
            flags.append("MARKDOWN_ARTIFACTS")
            score -= 30
        
        # Contains explanation text
        explanation_markers = ["Here is", "Here's", "Translation:", "Übersetzung:",
                               "Note:", "Hinweis:", "I have", "Ich habe"]
        for marker in explanation_markers:
            if marker in translation:
                flags.append(f"EXPLANATION_TEXT: '{marker}'")
                score -= 30
                break
        
        # Backslash/quote risk for string literals
        if segment and segment.get("token_type") == "STRING":
            if translation.count('"') % 2 != 0:
                flags.append("UNBALANCED_QUOTES")
                score -= 20
            if translation.count("'") % 2 != 0 and segment.get("quote_style") in ("'", "'''"):
                flags.append("UNBALANCED_SINGLE_QUOTES")
                score -= 20
    
    # === Determine status ===
    score = max(0, score)
    
    if hard_fail:
        status = "rejected"
    elif score >= 90:
        status = "auto-accepted"
    elif score >= 75:
        status = "spot-check"
    else:
        status = "manual-review"
    
    # Build validated entry
    validated = dict(entry)
    validated["score"] = score
    validated["status"] = status
    validated["flags"] = flags
    
    return validated


def generate_report(validated: list[dict], output_path: Path):
    """Generate a markdown review report."""
    # Statistics
    status_counts = defaultdict(int)
    kind_counts = defaultdict(lambda: defaultdict(int))
    flagged = []
    
    for entry in validated:
        status_counts[entry["status"]] += 1
        kind_counts[entry["kind"]][entry["status"]] += 1
        if entry["status"] in ("manual-review", "rejected", "spot-check"):
            flagged.append(entry)
    
    # Sort flagged by score (lowest first)
    flagged.sort(key=lambda x: x["score"])
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Translation Validation Report\n\n")
        
        # Summary
        total = len(validated)
        f.write("## Summary\n\n")
        f.write(f"| Status | Count | % |\n")
        f.write(f"|--------|-------|---|\n")
        for status in ["auto-accepted", "spot-check", "manual-review", "rejected"]:
            count = status_counts[status]
            pct = (count / total * 100) if total > 0 else 0
            f.write(f"| {status} | {count} | {pct:.1f}% |\n")
        f.write(f"| **Total** | **{total}** | **100%** |\n")
        f.write("\n")
        
        # By kind
        f.write("## By Kind\n\n")
        f.write("| Kind | Auto | Spot | Manual | Rejected |\n")
        f.write("|------|------|------|--------|----------|\n")
        for kind in sorted(kind_counts.keys()):
            kc = kind_counts[kind]
            f.write(f"| {kind} | {kc['auto-accepted']} | {kc['spot-check']} | {kc['manual-review']} | {kc['rejected']} |\n")
        f.write("\n")
        
        # Flagged items (only show first 100)
        if flagged:
            f.write(f"## Flagged Items ({len(flagged)} total, showing first 100)\n\n")
            f.write("| Score | Kind | ID | Flags | Source (first 60) | Translation (first 60) |\n")
            f.write("|-------|------|----|----|--------|-------------|\n")
            for entry in flagged[:100]:
                src_short = entry["source_text"][:60].replace("|", "\\|").replace("\n", " ")
                trans_short = entry.get("translation", "")[:60].replace("|", "\\|").replace("\n", " ")
                flags_str = "; ".join(entry["flags"])[:80]
                f.write(f"| {entry['score']} | {entry['kind']} | `{entry['id'][-40:]}` | {flags_str} | {src_short} | {trans_short} |\n")
        
        f.write("\n---\n")
        f.write(f"Generated from {total} translation entries.\n")
    
    print(f"Report written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Validate translations before patching")
    parser.add_argument("--input", "-i", default="scripts/i18n/output/translations.jsonl",
                        help="Input translations JSONL")
    parser.add_argument("--segments", "-s", default="scripts/i18n/output/segments.jsonl",
                        help="Original segments JSONL (for metadata)")
    parser.add_argument("--output", "-o", default="scripts/i18n/output/translations_validated.jsonl",
                        help="Output validated JSONL")
    parser.add_argument("--report", default="scripts/i18n/output/validation_report.md",
                        help="Output validation report (markdown)")
    args = parser.parse_args()
    
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent
    
    input_path = project_root / args.input
    segments_path = project_root / args.segments
    output_path = project_root / args.output
    report_path = project_root / args.report
    
    if not input_path.exists():
        print(f"ERROR: Translations file not found: {input_path}", file=sys.stderr)
        print("Run translate.py first.", file=sys.stderr)
        sys.exit(1)
    
    # Load segments for metadata lookup
    segments_index = {}
    if segments_path.exists():
        with open(segments_path, 'r', encoding='utf-8') as f:
            for line in f:
                seg = json.loads(line.strip())
                segments_index[seg["id"]] = seg
    
    # Load translations
    translations = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                translations.append(json.loads(line))
    
    print(f"Validating {len(translations)} translations...")
    
    # Validate each entry
    validated = []
    for entry in translations:
        segment = segments_index.get(entry["id"])
        result = validate_entry(entry, segment)
        validated.append(result)
    
    # Write validated JSONL
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for entry in validated:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    # Generate report
    generate_report(validated, report_path)
    
    # Print summary
    status_counts = defaultdict(int)
    for entry in validated:
        status_counts[entry["status"]] += 1
    
    print(f"\nResults:")
    print(f"  auto-accepted: {status_counts['auto-accepted']}")
    print(f"  spot-check:    {status_counts['spot-check']}")
    print(f"  manual-review: {status_counts['manual-review']}")
    print(f"  rejected:      {status_counts['rejected']}")
    print(f"\nOutput: {output_path}")


if __name__ == "__main__":
    main()
