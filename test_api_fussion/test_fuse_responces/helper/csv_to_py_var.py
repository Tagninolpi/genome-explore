#!/usr/bin/env bash
# Build a field-mapping variable from field_mapping_full.csv and put it in ../field_mappings.py
# Run ./csv_to_py.sh -h for the help.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
CSV_FILE="$SCRIPT_DIR/field_mapping_full.csv"
PY_FILE="$(cd "$SCRIPT_DIR/.." && pwd)/field_mappings.py"

usage() {
    cat <<'EOF'
csv_to_py.sh - turn field_mapping_full.csv into a variable of ../field_mappings.py

Usage:
    ./csv_to_py.sh VARIABLE_NAME
    ./csv_to_py.sh -h

How it works:
  1. Open field_mapping_full.csv (same folder as this script).
  2. In the "use" column, put  o  for the fields you want in the database
     search result and  x  for the ones you do not want. Only o and x are
     accepted, anything else is an error.
  3. Run  ./csv_to_py.sh MY_CONFIG . The fields marked o are written as the
     variable MY_CONFIG in ../field_mappings.py (the file must already exist).
     If MY_CONFIG already exists in that file it is overwritten; other
     variables are never touched.
  4. Use it in a search by passing the variable as the mapping:
         from field_mappings import MY_CONFIG
         fused = fuse(ncbi_record, gwh_record, MY_CONFIG)

The variable is a tuple of (global_name, ncbi_keys, gwh_keys) rows, built from
the NCBI_mapping and GWH_mapping columns (None when the field is not in that
database). You can keep several versions: use one variable name per version.

Current o / x arrangement:
  The o / x arrangement in the CSV (48 fields marked o) is the default and it
  works with the current code (fuse).
  If you mark more fields o, first check that they are compatible with the
  code, because the code does not account for every field yet. For example a
  field whose mapping goes through a list (a "[]" in NCBI_mapping or
  GWH_mapping) cannot be read and will always come out empty. This script only
  prints a warning for those, it does not stop you.
EOF
}

if [ "$#" -eq 0 ]; then
    usage
    exit 0
fi
case "$1" in
    -h|--help) usage; exit 0 ;;
    -*) echo "Error: unknown option '$1' (use -h for help)" >&2; exit 1 ;;
esac
if [ "$#" -ne 1 ]; then
    echo "Error: expected one argument, the variable name (use -h for help)" >&2
    exit 1
fi

python3 -I - "$CSV_FILE" "$PY_FILE" "$1" <<'PYEOF'
import ast
import csv
import json
import keyword
import re
import sys

csv_path, py_path, name = sys.argv[1:4]

if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or keyword.iskeyword(name):
    sys.exit(f"Error: '{name}' is not a valid Python variable name")

# ---- read and check the CSV ----
needed = ["global_name", "use", "NCBI_mapping", "GWH_mapping"]
try:
    f = open(csv_path, newline="", encoding="utf-8")
except FileNotFoundError:
    sys.exit(f"Error: CSV not found: {csv_path}")
with f:
    reader = csv.DictReader(f)
    missing = [c for c in needed if c not in (reader.fieldnames or [])]
    if missing:
        sys.exit(f"Error: {csv_path} is missing the column(s): {missing}")
    rows, excluded, list_fields = [], 0, []
    for line, row in enumerate(reader, start=2):
        gname = row["global_name"].strip()
        use = row["use"].strip().lower()
        if use not in ("o", "x"):
            sys.exit(f"Error: line {line} ({gname}): 'use' must be o or x, got '{row['use']}'")
        if use == "x":
            excluded += 1
            continue
        if not gname:
            sys.exit(f"Error: line {line}: empty global_name")
        keys = []
        for col in ("NCBI_mapping", "GWH_mapping"):
            cell = row[col].strip()
            if not cell:
                keys.append(None)
                continue
            try:
                value = json.loads(cell)
            except json.JSONDecodeError:
                sys.exit(f"Error: line {line} ({gname}): {col} is not a JSON list: {cell}")
            if not (isinstance(value, list) and value and all(isinstance(k, str) for k in value)):
                sys.exit(f"Error: line {line} ({gname}): {col} must be a non-empty list of keys: {cell}")
            keys.append(value)
        if keys[0] is None and keys[1] is None:
            sys.exit(f"Error: line {line}: {gname} has no mapping in either database")
        if any(k is not None and "[]" in k for k in keys):
            list_fields.append(gname)
        rows.append((gname, keys[0], keys[1]))

if not rows:
    sys.exit("Error: every field is marked x, nothing to write")
names = [r[0] for r in rows]
dupes = sorted({n for n in names if names.count(n) > 1})
if dupes:
    sys.exit(f"Error: duplicate global_name among the o rows: {dupes}")

# ---- build the variable ----
fmt = lambda keys: "None" if keys is None else json.dumps(keys)
body = "\n".join(f"    ({json.dumps(g)}, {fmt(n)}, {fmt(w)})," for g, n, w in rows)
block = f"{name} = (\n{body}\n)\n"

# ---- put it in the python file ----
try:
    text = open(py_path, encoding="utf-8").read()
except FileNotFoundError:
    sys.exit(f"Error: {py_path} does not exist; create it first (an empty file is fine)")
try:
    tree = ast.parse(text)
except SyntaxError as e:
    sys.exit(f"Error: {py_path} is not valid Python (line {e.lineno}), nothing written")

found = []
for node in tree.body:
    if isinstance(node, ast.Assign):
        targets = [t for t in node.targets if isinstance(t, ast.Name)]
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        targets = [node.target]
    else:
        continue
    if any(t.id == name for t in targets):
        found.append(node)

if len(found) > 1:
    sys.exit(f"Error: {name} is assigned {len(found)} times in {py_path}; fix it by hand first")
if found:
    lines = text.splitlines(keepends=True)
    node = found[0]
    new_text = "".join(lines[:node.lineno - 1]) + block + "".join(lines[node.end_lineno:])
    action = "replaced"
else:
    new_text = text
    if new_text and not new_text.endswith("\n"):
        new_text += "\n"
    if new_text.strip() and not new_text.endswith("\n\n"):
        new_text += "\n"
    new_text += block
    action = "added"

compile(new_text, py_path, "exec")  # never leave a broken file behind
with open(py_path, "w", encoding="utf-8") as f:
    f.write(new_text)

print(f"{action} {name}: {len(rows)} fields kept (o), {excluded} excluded (x) -> {py_path}")
if list_fields:
    shown = ", ".join(list_fields[:5]) + (", ..." if len(list_fields) > 5 else "")
    print(f"Warning: {len(list_fields)} kept field(s) read through a list ('[]') and fuse "
          f"cannot read those yet, they will come out empty: {shown}", file=sys.stderr)
PYEOF
