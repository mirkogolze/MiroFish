#!/usr/bin/env python3
"""
Retry failed translations one-at-a-time with strict timeout.
Reads batch files, finds untranslated segments, sends each individually.
"""
import json
import sys
import time
from pathlib import Path

import requests

API_URL = "http://localhost:1234/v1/chat/completions"
MODEL = "qwen2.5-14b-instruct"
TIMEOUT = 120  # strict 2-min timeout per item
OUTPUT = Path("/Users/olkr/Projects/MiroFish/scripts/i18n/output/translations.jsonl")
BATCHES_DIR = Path("/Users/olkr/Projects/MiroFish/scripts/i18n/output/batches")

SYSTEM_PROMPTS = {
    "comment": "You translate Chinese code comments to German. Return ONLY a JSON array with objects having 'id' and 'translation' fields. Keep technical terms, variable names, and code references unchanged. Be concise.",
    "docstring": "You translate Chinese Python docstrings to German. Return ONLY a JSON array with objects having 'id' and 'translation' fields. Preserve formatting, parameter references, RST/numpy-style markers. Keep technical terms in English where appropriate.",
    "fstring_text": "You translate Chinese f-string text segments to German. Return ONLY a JSON array with objects having 'id' and 'translation' fields. Preserve ALL placeholders like {variable} exactly. Keep the text natural in German.",
    "string_constant": "You translate Chinese string constants to German. Return ONLY a JSON array with objects having 'id' and 'translation' fields. Preserve formatting codes, placeholders, and special characters exactly.",
    "llm_prompt": "You translate Chinese LLM prompts to German. Return ONLY a JSON array with objects having 'id' and 'translation' fields. These are prompts that will be sent to AI models - translate the instructional content to German while preserving any template variables, formatting, and technical terminology.",
    "error_message": "You translate Chinese error messages to German. Return ONLY a JSON array with objects having 'id' and 'translation' fields. Keep technical terms, variable names, and format specifiers unchanged.",
}


def load_existing() -> set[str]:
    """Load IDs of already-translated segments."""
    ids = set()
    if OUTPUT.exists():
        with open(OUTPUT, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    ids.add(json.loads(line)["id"])
    return ids


def translate_single(item: dict, kind: str) -> dict | None:
    """Translate a single item. Returns translation dict or None."""
    system_prompt = SYSTEM_PROMPTS.get(kind, SYSTEM_PROMPTS["string_constant"])
    
    user_content = json.dumps({
        "task": "translate_zh_to_de",
        "items": [{"id": item["id"], "source_text": item["source_text"]}]
    }, ensure_ascii=False)
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
    }
    
    try:
        resp = requests.post(API_URL, json=payload, timeout=(10, TIMEOUT))
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        
        # Parse response
        text = content.strip()
        if text.startswith("```"):
            lines = text.split('\n')
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = '\n'.join(lines).strip()
        
        parsed = json.loads(text)
        if isinstance(parsed, list) and len(parsed) > 0:
            result = parsed[0]
            translation = result.get("translation") or result.get("source_text") or result.get("text")
            if translation:
                return {
                    "id": item["id"],
                    "source_text": item["source_text"],
                    "translation": translation,
                    "kind": kind,
                }
    except requests.exceptions.Timeout:
        print(f"      TIMEOUT")
    except json.JSONDecodeError:
        print(f"      PARSE ERROR")
    except Exception as e:
        print(f"      ERROR: {e}")
    
    return None


def main():
    existing = load_existing()
    print(f"Already translated: {len(existing)}")
    
    # Find missing items from batch files
    missing_items = []
    for batch_file in sorted(BATCHES_DIR.glob("batch_*.json")):
        with open(batch_file) as f:
            batch = json.load(f)
        kind = batch.get("kind", "string_constant")
        for item in batch["items"]:
            if item["id"] not in existing:
                missing_items.append((item, kind))
    
    print(f"Missing translations: {len(missing_items)}")
    if not missing_items:
        print("Nothing to do!")
        return
    
    # Translate one by one
    success = 0
    failed = 0
    
    with open(OUTPUT, 'a', encoding='utf-8') as out_f:
        for i, (item, kind) in enumerate(missing_items):
            print(f"  [{i+1}/{len(missing_items)}] {item['id'][:40]}... ", end="", flush=True)
            
            result = translate_single(item, kind)
            if result:
                out_f.write(json.dumps(result, ensure_ascii=False) + "\n")
                out_f.flush()
                success += 1
                print(f"✓")
            else:
                # Retry once
                time.sleep(2)
                result = translate_single(item, kind)
                if result:
                    out_f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    out_f.flush()
                    success += 1
                    print(f"✓ (retry)")
                else:
                    failed += 1
                    print(f"✗")
            
            time.sleep(0.5)  # Small delay between requests
    
    print(f"\n{'='*40}")
    print(f"Success: {success}")
    print(f"Failed:  {failed}")
    print(f"Total now: {len(existing) + success}")


if __name__ == "__main__":
    main()
