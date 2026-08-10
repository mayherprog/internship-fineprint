#!/usr/bin/env python3
"""The legal `sector` values, read from the schema rather than retyped.

`schema/program.schema.json` is the single source of truth. Everything else
that needs to know which sectors exist either reads the enum from here or is
checked against it:

  - tools/validate.py         rejects a record whose sector is not in the enum
  - tools/build.py            maps every enum value to a display heading
  - tools/ingest_research.py  keeps a research sector only if it is legal
  - web/src/types.ts          maps every enum value to a heading in the app

This module exists because the alternative failed in practice. On 2026-08-10
`private_equity` and `venture_capital` were briefly added to the schema alone
(neither is in the enum today). The new record passed schema validation and
then failed `tools/validate.py` with "sector is legal -- got 'private_equity'",
and two more files had to be patched by hand to agree with the first.

A display label is deliberately NOT derivable from the enum value: only a
human can decide that `banking_finance` reads as "Banking & finance". So the
label maps stay hand-written, and this module's job is to make an incomplete
one a loud failure instead of a heading that reads `private_equity`.

Failures here raise SystemExit on purpose. Every caller is a script, and
SystemExit is a BaseException, so a stray `except Exception` cannot turn a
drifted sector list back into a silent one.
"""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "program.schema.json"
WEB_TYPES_PATH = ROOT / "web" / "src" / "types.ts"


def load_sector_enum(schema_path=SCHEMA_PATH):
    """The sector enum, in the order the schema declares it.

    Raises rather than returning a default: a missing or malformed enum would
    otherwise make every downstream sector check silently accept everything.
    """
    schema_path = pathlib.Path(schema_path)
    try:
        raw = schema_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise SystemExit(f"{schema_path}: schema is not valid UTF-8 ({e})") from e
    except OSError as e:
        raise SystemExit(f"{schema_path}: cannot read the schema, so sectors "
                         f"cannot be resolved ({e})") from e
    try:
        schema = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(f"{schema_path}: schema is not valid JSON ({e})") from e

    node = schema.get("properties", {}).get("sector", {})
    values = node.get("enum") if isinstance(node, dict) else None
    if not isinstance(values, list) or not values:
        raise SystemExit(
            f"{schema_path}: properties.sector.enum is missing or empty; "
            "there is nothing to validate sectors against")
    if not all(isinstance(v, str) and v.strip() for v in values):
        raise SystemExit(
            f"{schema_path}: properties.sector.enum must be non-empty strings, got {values!r}")
    if len(set(values)) != len(values):
        raise SystemExit(f"{schema_path}: properties.sector.enum contains duplicates: {values!r}")
    return tuple(values)


SECTOR_ORDER = load_sector_enum()
SECTORS = frozenset(SECTOR_ORDER)


def assert_labels_cover_schema(labels, where, sectors=SECTORS):
    """Fail loudly unless `labels` has exactly one entry per schema sector.

    Both directions matter. A missing key renders a raw slug as a heading; an
    extra key is a label for a sector no record may legally carry, which is
    how a renamed enum value goes unnoticed.
    """
    have = set(labels)
    missing = sorted(sectors - have)
    extra = sorted(have - sectors)
    if not missing and not extra:
        return
    allowed = [s for s in SECTOR_ORDER if s in sectors]
    allowed += sorted(set(sectors) - set(SECTOR_ORDER))
    lines = [f"{where} disagrees with {SCHEMA_PATH.name} (properties.sector.enum):"]
    if missing:
        lines.append(f"  no display label for: {', '.join(missing)}")
    if extra:
        lines.append(f"  label for a sector the schema does not allow: {', '.join(extra)}")
    lines.append(f"  the allowed sectors are: {', '.join(allowed)}")
    raise SystemExit("\n".join(lines))


# A key is a bare identifier or a quoted string; a value is a double-quoted
# string. Anything else inside the literal -- a comment, a spread, a nested
# object, a computed key -- is deliberately left unmatched and reported as
# unparsed text. A parser that skipped what it did not understand would drop
# an entry silently, which is the failure this whole module exists to prevent.
_TS_ENTRY_RE = re.compile(
    r'([A-Za-z_$][\w$]*|"(?:[^"\\]|\\.)*")\s*:\s*("(?:[^"\\]|\\.)*")')


def _const_pattern(const_name):
    """Match `export const NAME[: Type] = { ... };` with `};` starting a line.

    Anchored at a line start so a commented-out declaration earlier in the file
    cannot be matched in place of the real one.
    """
    return (r"^export const " + re.escape(const_name) +
            r"\s*(?::[^=]*?)?=\s*\{(?P<body>.*?)^\};")


def parse_ts_label_map(source, const_name):
    """Pull a flat `key: "value"` TypeScript object literal out of source text.

    Deliberately strict: every failure raises, including text it merely does
    not recognise, because a partial result would turn the front-end check
    into a no-op that still reported success.
    """
    match = re.search(_const_pattern(const_name), source, re.S | re.M)
    if not match:
        raise SystemExit(
            f"could not find `export const {const_name}` as a flat object literal "
            "starting at column 0 and closing with `};` on its own line")

    body = match.group("body")
    labels, unparsed, cursor = {}, [], 0
    for entry in _TS_ENTRY_RE.finditer(body):
        unparsed.append(body[cursor:entry.start()])
        cursor = entry.end()
        key, value = entry.group(1), entry.group(2)
        if key.startswith('"'):
            key = json.loads(key)
        try:
            labels[key] = json.loads(value)
        except json.JSONDecodeError as e:
            raise SystemExit(
                f"{const_name}: cannot read the value for {key}: {value} ({e})") from e
    unparsed.append(body[cursor:])

    leftover = "".join(unparsed).replace(",", "").strip()
    if leftover:
        raise SystemExit(
            f"{const_name}: this is not a flat `key: \"value\"` map. Unparsed: "
            f"{leftover[:100]!r}. Comments, nested objects, spreads and single "
            "quotes are rejected rather than skipped, so that no entry can go "
            "missing without anyone noticing.")
    if not labels:
        raise SystemExit(f"{const_name}: parsed no entries")
    return labels


def assert_web_labels_match(python_labels, types_path=WEB_TYPES_PATH, const_name="SECTOR_LABEL"):
    """The front end keeps its own label map; check it instead of trusting it.

    Its keys must be exactly the schema enum, for the same reason build.py's
    must be. Its values must match the Python map too: one sector rendering as
    "Banking & finance" in TABLE.md and "Banking and finance" in the app is
    the same duplication bug wearing different clothes.

    This checks the label map only. Whether the *data* carries a legal sector
    is build.load()'s job, and export_json.py runs that too.
    """
    types_path = pathlib.Path(types_path)
    if not types_path.exists():
        raise SystemExit(f"{types_path}: front-end types not found; cannot check {const_name}")
    where = f"{types_path.relative_to(ROOT)} {const_name}"
    labels = parse_ts_label_map(types_path.read_text(encoding="utf-8"), const_name)
    assert_labels_cover_schema(labels, where)

    differing = sorted(s for s in SECTOR_ORDER if labels[s] != python_labels.get(s))
    if differing:
        detail = "\n".join(
            f"    {s}: python {python_labels.get(s)!r} vs typescript {labels[s]!r}"
            for s in differing)
        raise SystemExit(
            f"{where} renders sectors differently from tools/build.py SECTOR_LABEL:\n{detail}")
    return labels


if __name__ == "__main__":
    for sector in SECTOR_ORDER:
        print(sector)
