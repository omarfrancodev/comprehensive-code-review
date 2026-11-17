"""Named canonical encodings used by durable CCR documents."""
import json


def archive_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def compact_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def receipt_bytes(value: object) -> bytes:
    return compact_bytes(value) + b"\n"


def decode_json(data):
    """Decode UTF-8 JSON bytes and reject duplicate keys and nonfinite constants."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('nonfinite JSON number: ' + value)

    return json.loads(data.decode('utf-8'), object_pairs_hook=unique, parse_constant=invalid_constant)
