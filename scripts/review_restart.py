"""Compatibility facade for durable restart contracts."""
from ccr.archive.restart_contract import (
    INTENT_VERSION, INTENT_FIELDS, SOURCE_FIELDS, SUCCESSOR_FIELDS, REQUEST_FIELDS,
    _json, _sha, _bounded_text, _input_object, _path, _normalize_controller,
    _normalize_harness, normalize_restart_request, _request_identity,
    same_restart_request, _source_key, build_restart_intent, validate_restart_intent,
)
