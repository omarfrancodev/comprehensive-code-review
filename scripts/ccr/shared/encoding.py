"""Named canonical encodings used by durable CCR documents."""
import json


def archive_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def compact_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def receipt_bytes(value: object) -> bytes:
    return compact_bytes(value) + b"\n"
