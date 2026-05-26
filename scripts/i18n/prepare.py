#!/usr/bin/env python3
"""
Phase 2: Prepare translation batches from extracted segments.

Groups segments by kind, forms batches with appropriate sizes,
and writes JSON batch files ready for LLM translation.

Usage:
    python scripts/i18n/prepare.py [--input PATH] [--output-dir PATH] [--batch-size N]
"""
import argparse
import json
import os
import sys
from pathlib import Path
from collections import defaultdict

# Batch sizes per kind (smaller = more context per item, less hallucination risk)
DEFAULT_BATCH_SIZES = {
    "comment": 40,
    "docstring": 20,
    "log_message": 30,
    "error_message": 30,
    "fstring_text": 25,
    "llm_prompt": 5,
    "argparse_help": 30,
    "string_constant": 30,
}

# System prompt templates per kind
SYSTEM_PROMPTS = {
    "comment": (
        "Du übersetzt Python-Kommentare vom Chinesischen ins Deutsche. "
        "Regeln: Kurz und prägnant. Imperativ-Stil bevorzugen. "
        "Keine Vollsätze nötig. Technische Begriffe in der protected_terms-Liste NICHT übersetzen. "
        "Gib NUR das JSON-Array zurück, keine Erklärung."
    ),
    "docstring": (
        "Du übersetzt Python-Docstrings vom Chinesischen ins Deutsche. "
        "Regeln: Strukturiert und technisch korrekt. Erste Zeile = Kurzbeschreibung. "
        "Args/Returns/Raises-Abschnitte beibehalten. "
        "Platzhalter {…} und technische Begriffe aus protected_terms EXAKT beibehalten. "
        "Gib NUR das JSON-Array zurück."
    ),
    "log_message": (
        "Du übersetzt Python-Log-Nachrichten vom Chinesischen ins Deutsche. "
        "Regeln: Sachlich und kurz. Keine Füllwörter. "
        "Platzhalter {…} EXAKT beibehalten. Technische Begriffe nicht übersetzen. "
        "Gib NUR das JSON-Array zurück."
    ),
    "error_message": (
        "Du übersetzt Python-Fehlermeldungen vom Chinesischen ins Deutsche. "
        "Regeln: Präzise und klar. Platzhalter {…} EXAKT beibehalten. "
        "Technische Begriffe aus protected_terms nicht übersetzen. "
        "Gib NUR das JSON-Array zurück."
    ),
    "fstring_text": (
        "Du übersetzt f-String-Textteile vom Chinesischen ins Deutsche. "
        "KRITISCH: Platzhalter wie {variable}, {expr!r}, {expr:fmt} MÜSSEN exakt so bleiben. "
        "Nur den chinesischen Text zwischen den Platzhaltern übersetzen. "
        "Technische Begriffe aus protected_terms nicht übersetzen. "
        "Gib NUR das JSON-Array zurück."
    ),
    "llm_prompt": (
        "Du übersetzt LLM-System-Prompts vom Chinesischen ins Deutsche. "
        "WICHTIG: Instruktions-Struktur exakt beibehalten (Nummerierung, Aufzählungen, 【】-Marker). "
        "Platzhalter {…} EXAKT beibehalten. Technische Begriffe nicht übersetzen. "
        "Nicht zu frei umformulieren — die Prompt-Logik muss erhalten bleiben. "
        "Gib NUR das JSON-Array zurück."
    ),
    "argparse_help": (
        "Du übersetzt argparse-Hilfetexte vom Chinesischen ins Deutsche. "
        "Regeln: Kurz, user-facing verständlich. "
        "Platzhalter und technische Begriffe beibehalten. "
        "Gib NUR das JSON-Array zurück."
    ),
    "string_constant": (
        "Du übersetzt Python-String-Konstanten vom Chinesischen ins Deutsche. "
        "Regeln: Natürliches Deutsch, aber prägnant. "
        "Platzhalter {…}, %s, %(name)s EXAKT beibehalten. "
        "Technische Begriffe aus protected_terms nicht übersetzen. "
        "Gib NUR das JSON-Array zurück."
    ),
}

# Translation rules (shared across all batch files)
TRANSLATION_RULES = [
    "Return ONLY a valid JSON array.",
    "Preserve every 'id' field exactly as given.",
    "Translate only 'source_text' into German.",
    "Preserve ALL placeholders exactly ({var}, {var!r}, {var:fmt}, %s, %(name)s).",
    "Do NOT translate terms listed in 'protected_terms'.",
    "Do NOT add explanations, comments, or markdown.",
    "German should be natural but concise.",
    "For comments, prefer short infinitive style (e.g. 'Datenbankverbindung initialisieren').",
    "Keep 【】brackets and their structure if present.",
]


def load_segments(input_path: Path) -> list[dict]:
    """Load segments from JSONL file."""
    segments = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                segments.append(json.loads(line))
    return segments


def build_dedup_index(segments: list[dict]) -> dict[str, list[str]]:
    """
    Build a dedup index: normalized source_text → list of segment IDs.
    Segments with identical source text get the same translation.
    """
    index = defaultdict(list)
    for seg in segments:
        # Normalize: strip whitespace
        key = seg["source_text"].strip()
        index[key].append(seg["id"])
    return dict(index)


def create_batch_item(seg: dict) -> dict:
    """Create a batch item from a segment (subset of fields for LLM)."""
    item = {
        "id": seg["id"],
        "kind": seg["kind"],
        "source_text": seg["source_text"],
    }
    
    if seg["placeholders"]:
        item["placeholders"] = seg["placeholders"]
    
    if seg["protected_terms"]:
        item["protected_terms"] = seg["protected_terms"]
    
    # Add context for complex types
    if seg["kind"] in ("llm_prompt", "docstring", "fstring_text"):
        context = seg.get("context_before", "")
        if context:
            item["context"] = context[:200]  # Truncate long context
    
    return item


def form_batches(segments: list[dict], batch_size_override: int | None = None) -> list[dict]:
    """
    Group segments by kind, form batches, and create batch files.
    Returns a list of batch dicts ready for writing.
    """
    # Group by kind
    by_kind = defaultdict(list)
    for seg in segments:
        by_kind[seg["kind"]].append(seg)
    
    batches = []
    batch_num = 0
    
    for kind, kind_segments in sorted(by_kind.items()):
        batch_size = batch_size_override or DEFAULT_BATCH_SIZES.get(kind, 30)
        
        # Split into batches
        for i in range(0, len(kind_segments), batch_size):
            chunk = kind_segments[i:i + batch_size]
            batch_num += 1
            
            items = [create_batch_item(seg) for seg in chunk]
            
            batch = {
                "batch_id": f"batch_{batch_num:04d}",
                "kind": kind,
                "system_prompt": SYSTEM_PROMPTS.get(kind, SYSTEM_PROMPTS["string_constant"]),
                "rules": TRANSLATION_RULES,
                "item_count": len(items),
                "items": items,
            }
            
            batches.append(batch)
    
    return batches


def write_dedup_index(dedup_index: dict, output_dir: Path):
    """Write dedup index for later use in translation phase."""
    # Only write entries with duplicates
    dupes = {k: v for k, v in dedup_index.items() if len(v) > 1}
    
    output_path = output_dir / "dedup_index.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dupes, f, ensure_ascii=False, indent=2)
    
    print(f"Dedup index: {len(dupes)} duplicate source texts (covering {sum(len(v) for v in dupes.values())} segments)")


def main():
    parser = argparse.ArgumentParser(description="Prepare translation batches from extracted segments")
    parser.add_argument("--input", "-i", default="scripts/i18n/output/segments.jsonl",
                        help="Input JSONL file from extract phase")
    parser.add_argument("--output-dir", "-o", default="scripts/i18n/output/batches",
                        help="Output directory for batch JSON files")
    parser.add_argument("--batch-size", type=int, default=None,
                        help="Override batch size for all kinds")
    args = parser.parse_args()
    
    # Resolve paths relative to project root
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent
    
    input_path = project_root / args.input
    output_dir = project_root / args.output_dir
    
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        print("Run extract.py first.", file=sys.stderr)
        sys.exit(1)
    
    # Load segments
    segments = load_segments(input_path)
    print(f"Loaded {len(segments)} segments from {input_path.name}")
    
    # Build dedup index
    dedup_index = build_dedup_index(segments)
    unique_count = len(dedup_index)
    dupe_count = len(segments) - unique_count
    print(f"Unique texts: {unique_count}, duplicates: {dupe_count}")
    
    # Deduplicate: only translate first occurrence of each unique text
    seen_texts = set()
    unique_segments = []
    for seg in segments:
        key = seg["source_text"].strip()
        if key not in seen_texts:
            seen_texts.add(key)
            unique_segments.append(seg)
    
    print(f"Segments to translate (after dedup): {len(unique_segments)}")
    
    # Form batches
    batches = form_batches(unique_segments, args.batch_size)
    
    # Write batch files
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean old batches
    for old_file in output_dir.glob("batch_*.json"):
        old_file.unlink()
    
    for batch in batches:
        batch_path = output_dir / f"{batch['batch_id']}.json"
        with open(batch_path, 'w', encoding='utf-8') as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)
    
    # Write dedup index
    write_dedup_index(dedup_index, output_dir.parent)
    
    # Statistics
    print(f"\nCreated {len(batches)} batch files in {output_dir}/")
    print("\nBatches by kind:")
    kind_stats = defaultdict(lambda: {"batches": 0, "items": 0})
    for batch in batches:
        kind_stats[batch["kind"]]["batches"] += 1
        kind_stats[batch["kind"]]["items"] += batch["item_count"]
    
    for kind, stats in sorted(kind_stats.items(), key=lambda x: -x[1]["items"]):
        print(f"  {kind}: {stats['batches']} batches, {stats['items']} items")


if __name__ == "__main__":
    main()
