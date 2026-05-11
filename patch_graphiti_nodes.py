"""
Build-time patch for graphiti-core EntityNode.save.

Applied during Docker image build (see Dockerfile).

Problem:
  The LLM sometimes returns a JSON-Schema dict ({"title": "...", "type": "string",
  "description": "..."}) instead of a real string value for entity properties like
  `summary`.  graphiti-core merges those into entity_data and passes them straight
  to Neo4j which rejects non-primitive property values with a TypeError.

Fix:
  Wrap EntityNode.save so that any dict/list value in entity_data is JSON-serialised
  to a string before the Neo4j write.  Adds WARNING-level log lines for each
  conversion so operators can see when (and what) the LLM echoes as schema dicts.
"""

import pathlib
import sys


PATCH_MARKER = "# --- graphiti-neo4j-compat patch applied ---"

OLD = "        entity_data.update(self.attributes or {})"

NEW = '''\
        # --- begin graphiti-neo4j-compat patch ---
        # graphiti-neo4j-compat patch applied
        import json as _json_nc
        import logging as _log_nc
        _nc_log = _log_nc.getLogger("graphiti.nodes.patch")
        # Fix summary *before* attribute merge (may also come from LLM)
        if isinstance(entity_data.get("summary"), (dict, list)):
            _nc_log.warning(
                "EntityNode.save: summary is %s (LLM schema echo?) — serialising to JSON. Value: %s",
                type(entity_data["summary"]).__name__, entity_data["summary"]
            )
            entity_data["summary"] = _json_nc.dumps(entity_data["summary"])
        # Fix attributes
        _raw_attrs = self.attributes or {}
        _safe_attrs = {}
        for _k, _v in _raw_attrs.items():
            if isinstance(_v, (dict, list)):
                _nc_log.warning(
                    "EntityNode.save: attr[%s] is %s (LLM schema echo?) — serialising to JSON. Value: %s",
                    _k, type(_v).__name__, _v
                )
                _safe_attrs[_k] = _json_nc.dumps(_v)
            else:
                _safe_attrs[_k] = _v
        _nc_log.debug("EntityNode.save entity_data keys before Neo4j write: %s", list(entity_data.keys()))
        _nc_log.debug("EntityNode.save entity_data values: %s", entity_data)
        # --- end graphiti-neo4j-compat patch ---
        entity_data.update(_safe_attrs)'''


def main() -> None:
    venv_dirs = list(pathlib.Path(".venv").rglob("graphiti_core/nodes.py"))
    if not venv_dirs:
        print("ERROR: graphiti_core/nodes.py not found in .venv", file=sys.stderr)
        sys.exit(1)

    nodes_path = venv_dirs[0]
    src = nodes_path.read_text()

    if PATCH_MARKER in src:
        print(f"Already patched: {nodes_path}")
        return

    if OLD not in src:
        print(f"ERROR: patch target not found in {nodes_path}", file=sys.stderr)
        print("First 200 chars of file:", src[:200], file=sys.stderr)
        sys.exit(1)

    patched = src.replace(OLD, NEW)
    nodes_path.write_text(patched)

    # Remove stale bytecode
    pyc_dir = nodes_path.parent / "__pycache__"
    removed = 0
    for f in pyc_dir.glob("nodes.cpython-*.pyc"):
        f.unlink()
        removed += 1

    print(f"Patched {nodes_path} — removed {removed} .pyc file(s)")


if __name__ == "__main__":
    main()
