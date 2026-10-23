"""Pinned review-scope validation with diagnostics shared across pure contracts."""

SCOPE_FIELDS = {"repository", "mode", "base", "head", "snapshot", "target", "reference"}
MODES = {"pr", "mr", "commit", "range", "staged", "unstaged", "working", "module", "feature"}


def validate_scope(scope: object) -> list[str]:
    errors = []

    def error(path, message):
        errors.append(f"{path}: {message}")

    def fields(value, names, path):
        if not isinstance(value, dict):
            error(path, "expected object")
            return {}
        for name in names:
            if name not in value:
                error(f"{path}.{name}", "required field missing")
        for name in value:
            if name not in names:
                error(f"{path}.{name}", "unknown field")
        return value

    def text(value, path, nullable=False):
        if nullable and value is None:
            return
        if not isinstance(value, str) or not value.strip():
            error(path, "expected nonempty text")

    def enum(value, choices, path):
        if not isinstance(value, str) or value not in choices:
            error(path, "invalid value")

    value = fields(scope, SCOPE_FIELDS, "scope")
    text(value.get("repository"), "scope.repository")
    enum(value.get("mode"), MODES, "scope.mode")
    for key in ("base", "head", "snapshot", "target", "reference"):
        text(value.get(key), f"scope.{key}", nullable=True)
    if not value.get("head") and not value.get("snapshot"):
        error("scope", "head or snapshot identity required")
    if isinstance(value.get("mode"), str) and value["mode"] in {"staged", "unstaged", "working"} and not value.get("snapshot"):
        error("scope.snapshot", "local edits require captured snapshot identity")
    return errors


def require_scope(scope: object) -> None:
    if not isinstance(scope, dict) or set(scope) != SCOPE_FIELDS:
        raise ValueError("scope must contain exactly the pinned scope fields")
    errors = validate_scope(scope)
    if errors:
        raise ValueError("; ".join(errors))
