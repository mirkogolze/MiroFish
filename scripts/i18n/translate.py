#!/usr/bin/env python3
"""
Phase 3: Translate batches via LLM (LM Studio or OpenAI-compatible API).

Sends prepared batch files to a local LLM and stores translations in a JSONL file.
Resume-capable: skips already-translated segment IDs.

Usage:
    python scripts/i18n/translate.py [--api-url URL] [--model MODEL] [--resume] [--dry-run]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from collections import defaultdict

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


DEFAULT_API_URL = "http://localhost:1234/v1"
DEFAULT_MODEL = "qwen2.5-14b-instruct"  # LM Studio local


def load_existing_translations(output_path: Path) -> dict[str, dict]:
    """Load already-translated segments from output JSONL."""
    existing = {}
    if output_path.exists():
        with open(output_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    existing[entry["id"]] = entry
    return existing


def build_user_prompt(batch: dict) -> str:
    """Build the user prompt from a batch file."""
    items_for_prompt = []
    for item in batch["items"]:
        prompt_item = {"id": item["id"], "source_text": item["source_text"]}
        if "placeholders" in item and item["placeholders"]:
            prompt_item["placeholders"] = item["placeholders"]
        if "protected_terms" in item and item["protected_terms"]:
            prompt_item["protected_terms"] = item["protected_terms"]
        if "context" in item:
            prompt_item["context"] = item["context"]
        items_for_prompt.append(prompt_item)
    
    payload = {
        "task": "translate_zh_to_de",
        "rules": batch["rules"],
        "items": items_for_prompt,
    }
    
    return json.dumps(payload, ensure_ascii=False, indent=2)


def call_llm(api_url: str, model: str, system_prompt: str, user_prompt: str,
             temperature: float = 0.1, max_retries: int = 3) -> str | None:
    """Call LLM API and return raw response text."""
    url = f"{api_url}/chat/completions"
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": 4096,
    }
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, timeout=600)
            resp.raise_for_status()
            data = resp.json()
            
            content = data["choices"][0]["message"]["content"]
            return content
            
        except requests.exceptions.Timeout:
            print(f"    Timeout (attempt {attempt + 1}/{max_retries})")
            time.sleep(5)
        except requests.exceptions.ConnectionError:
            print(f"    Connection error (attempt {attempt + 1}/{max_retries})")
            time.sleep(10)
        except (requests.exceptions.HTTPError, KeyError, IndexError) as e:
            print(f"    API error: {e} (attempt {attempt + 1}/{max_retries})")
            time.sleep(5)
    
    return None


def parse_llm_response(response_text: str, expected_ids: set[str]) -> list[dict] | None:
    """
    Parse LLM response into translation items.
    Handles various response formats (JSON array, wrapped in markdown, etc.)
    """
    if not response_text:
        return None
    
    text = response_text.strip()
    
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split('\n')
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = '\n'.join(lines).strip()
    
    # Try parsing as JSON
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in the response
        start = text.find('[')
        end = text.rfind(']')
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
        else:
            return None
    
    # Handle both formats: direct array or {items: [...]}
    if isinstance(parsed, dict) and "items" in parsed:
        parsed = parsed["items"]
    
    if not isinstance(parsed, list):
        return None
    
    # Validate each item
    valid_items = []
    for item in parsed:
        if not isinstance(item, dict) or "id" not in item:
            continue
        # LLM may use "translation" or "source_text" as the translated field
        translation = item.get("translation") or item.get("source_text") or item.get("text")
        if translation and item["id"] in expected_ids:
            valid_items.append({"id": item["id"], "translation": translation})
    
    return valid_items if valid_items else None


def translate_batch(batch: dict, api_url: str, model: str, existing: dict,
                    dry_run: bool = False) -> list[dict]:
    """Translate a single batch and return translation entries."""
    # Filter out already-translated items
    items_to_translate = [item for item in batch["items"] if item["id"] not in existing]
    
    if not items_to_translate:
        return []
    
    # Create a modified batch with only untranslated items
    batch_copy = dict(batch)
    batch_copy["items"] = items_to_translate
    
    system_prompt = batch["system_prompt"]
    user_prompt = build_user_prompt(batch_copy)
    
    if dry_run:
        print(f"    [DRY RUN] Would send {len(items_to_translate)} items")
        print(f"    System prompt: {system_prompt[:80]}...")
        print(f"    User prompt length: {len(user_prompt)} chars")
        return []
    
    # Call LLM
    response = call_llm(api_url, model, system_prompt, user_prompt)
    
    if response is None:
        print(f"    ERROR: No response from LLM")
        return []
    
    # Parse response
    expected_ids = {item["id"] for item in items_to_translate}
    translations = parse_llm_response(response, expected_ids)
    
    if translations is None:
        print(f"    ERROR: Could not parse LLM response")
        # Save raw response for debugging
        return []
    
    # Build result entries with metadata
    results = []
    for trans in translations:
        # Find original item for metadata
        orig_item = next((item for item in items_to_translate if item["id"] == trans["id"]), None)
        if orig_item:
            entry = {
                "id": trans["id"],
                "kind": batch["kind"],
                "source_text": orig_item["source_text"],
                "translation": trans["translation"],
                "batch_id": batch["batch_id"],
            }
            results.append(entry)
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Translate batches via LLM")
    parser.add_argument("--api-url", default=DEFAULT_API_URL,
                        help=f"LLM API base URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--input-dir", default="scripts/i18n/output/batches",
                        help="Directory with batch JSON files")
    parser.add_argument("--output", "-o", default="scripts/i18n/output/translations.jsonl",
                        help="Output JSONL file for translations")
    parser.add_argument("--resume", action="store_true", default=True,
                        help="Skip already-translated segments (default: True)")
    parser.add_argument("--no-resume", action="store_true",
                        help="Re-translate all segments (overwrite existing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be sent without calling LLM")
    parser.add_argument("--batch", help="Translate only a specific batch file (e.g. batch_0001)")
    parser.add_argument("--temperature", type=float, default=0.1,
                        help="LLM temperature (default: 0.1)")
    args = parser.parse_args()
    
    # Resolve paths
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent
    
    input_dir = project_root / args.input_dir
    output_path = project_root / args.output
    
    if not input_dir.exists():
        print(f"ERROR: Batch directory not found: {input_dir}", file=sys.stderr)
        print("Run prepare.py first.", file=sys.stderr)
        sys.exit(1)
    
    # Load existing translations for resume
    existing = {}
    if not args.no_resume:
        existing = load_existing_translations(output_path)
        if existing:
            print(f"Resume mode: {len(existing)} segments already translated")
    
    # Load batch files
    if args.batch:
        batch_files = [input_dir / f"{args.batch}.json"]
        if not batch_files[0].exists():
            print(f"ERROR: Batch file not found: {batch_files[0]}", file=sys.stderr)
            sys.exit(1)
    else:
        batch_files = sorted(input_dir.glob("batch_*.json"))
    
    if not batch_files:
        print("No batch files found.", file=sys.stderr)
        sys.exit(1)
    
    print(f"Processing {len(batch_files)} batch files...")
    print(f"API: {args.api_url}")
    print(f"Model: {args.model}")
    print()
    
    # Process batches
    total_translated = 0
    total_failed = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    for batch_file in batch_files:
        with open(batch_file, 'r', encoding='utf-8') as f:
            batch = json.load(f)
        
        # Count remaining items
        remaining = sum(1 for item in batch["items"] if item["id"] not in existing)
        if remaining == 0:
            continue
        
        print(f"  {batch['batch_id']} ({batch['kind']}): {remaining} items...", end=" ", flush=True)
        
        results = translate_batch(batch, args.api_url, args.model, existing, args.dry_run)
        
        if results:
            # Append to output file
            with open(output_path, 'a', encoding='utf-8') as f:
                for entry in results:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            
            # Update existing dict for resume
            for entry in results:
                existing[entry["id"]] = entry
            
            total_translated += len(results)
            expected = remaining
            if len(results) < expected:
                missed = expected - len(results)
                total_failed += missed
                print(f"✓ {len(results)}/{expected} (missed {missed})")
            else:
                print(f"✓ {len(results)}")
        elif not args.dry_run:
            total_failed += remaining
            print(f"✗ FAILED")
    
    # Summary
    print(f"\n{'=' * 40}")
    print(f"Translated: {total_translated}")
    print(f"Failed: {total_failed}")
    print(f"Total in memory: {len(existing)}")
    if output_path.exists():
        print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
