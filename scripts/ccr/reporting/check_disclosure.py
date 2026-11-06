"""One proof-validated public check view for every audience."""
from ccr.contracts.check_disclosure import (canonical, digest, safe_text, private_values,
                                           validate_check_disclosure)


def sanitize_public_detail(value, secrets, *, syntax='prose', explanation=False):
    from ccr.contracts.check_disclosure import sanitize_projected_detail
    if not isinstance(value, str):
        return value
    value = sanitize_projected_detail(value, secrets, syntax=syntax)
    if explanation:
        from ccr.reporting.text_projection import omit_private_detail_paths
        value = omit_private_detail_paths(value)
    return value


def project_check_disclosure(record, disclosure, sources, input_identity, *, _legacy=False):
    from ccr.contracts.check_disclosure import _legacy_safe_text
    sanitize = _legacy_safe_text if _legacy else sanitize_public_detail
    errors = validate_check_disclosure(record, disclosure, sources, input_identity, _legacy_only=_legacy)
    if errors:
        raise ValueError('; '.join(errors))
    raw = sources.get('evidence/check-disclosure.json')
    if raw is not None:
        import json
        if json.loads(raw) != disclosure:
            raise ValueError('selected check disclosure bytes differ from the supplied sidecar')
    if _legacy:
        secrets = private_values(record, None, sources)
    else:
        from ccr.reporting.projections import public_sensitive_values
        secrets = public_sensitive_values(record, sources=sources, editorial_texts=(disclosure,))
    sanitize_explanation = sanitize if _legacy else lambda value, secrets: sanitize(value, secrets, explanation=True)
    return dict(source_sha256=disclosure['source_sha256'], check_disclosure_sha256=digest(raw if raw is not None else canonical(disclosure)),
        checks=[dict(id=row['id'], mode=row['mode'], command=sanitize(row['command'], secrets),
                     resources=[sanitize(resource['path'], secrets) for resource in row['resources']],
                     explanation=sanitize_explanation(row['explanation'], secrets)) for row in disclosure['checks']])


def disclosure_view(record, context, sources, *, _legacy=False):
    if context is None:
        if record.get('schema_version') in (12, 13) and record.get('checks'):
            raise ValueError('check disclosure context required for schema 12/13 checks')
        return None
    sources = sources or {}
    identity = context.get('input_identity', {})
    expected = getattr(sources, 'input_identity', None)
    if expected is not None and expected != identity:
        raise ValueError('disclosure identity differs from the independently pinned archive input')
    if expected is None:
        # A sidecar/catalog's own hash assertion is not an initial snapshot anchor.
        # Standalone publication requires verifiable Git objects at scope.head.
        import json
        from ccr.contracts.check_disclosure import _git_membership
        for row in context.get('checks', []):
            if row.get('resources'):
                raw = sources.get(row.get('execution_reference'))
                execution = json.loads(raw) if isinstance(raw, bytes) else {}
                proved = set()
                for resource in execution.get('resources', []):
                    try:
                        content = bytes.fromhex(resource.get('content', ''))
                    except (ValueError, TypeError):
                        continue
                    if (_git_membership(record['scope']['head'], resource.get('path', ''), content, resource.get('git_objects'))
                            and digest(content) == resource.get('executed_sha256')):
                        proved.add((resource['path'], digest(content), resource['executed_sha256']))
                if any((resource['path'], resource['project_sha256'], resource['executed_sha256']) not in proved for resource in row['resources']):
                    raise ValueError('snapshot disclosure requires an independently registered initial input anchor')
    return project_check_disclosure(record, context, sources, expected or identity, _legacy=_legacy)


def disclosure_lines(row, *, format_text=None, format_proven=None):
    from ccr.reporting.markdown import markdown_text
    format_text = format_text or markdown_text
    format_proven = format_proven or format_text
    lines = []
    if row['command']:
        lines.append('  - **Comando saneado:** ' + format_proven(row['command']))
    if row['resources']:
        lines.append('  - **Recursos del proyecto:** ' + '; '.join(format_proven(path) for path in row['resources']))
    lines.append('  - **Explicación del check:** ' + format_text(row['explanation']))
    return lines
