"""Compatibility facade for retained-reference contracts."""
from ccr.contracts.reference_types import *
from ccr.contracts.reference_types import _issue
from ccr.contracts.references import *
from ccr.contracts.references import _safe_component
from ccr.contracts.reference_index import *
from ccr.contracts.reference_index import _is_sha256, _ordered_issues, _selected_bytes
from ccr.contracts.semantic_references import validate_semantic_references
from ccr.contracts.material_inputs import validate_material_inputs
