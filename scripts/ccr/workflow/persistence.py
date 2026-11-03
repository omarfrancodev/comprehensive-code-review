"""Proportional persistence selection from explicitly observed review facts."""

_REQUIRED_TRUE = (
    ('inputs_pinned', 'identidad de entradas sin fijar'),
    ('scope_identified', 'alcance no identificado'),
    ('requirements_known', 'requisitos desconocidos'),
    ('consumers_known', 'consumidores desconocidos'),
    ('bounded_flows', 'flujos sin delimitar'),
    ('evidence_preservable', 'evidencia necesaria no acreditada'),
    ('privacy_preservable', 'privacidad no acreditada'),
)
_REQUIRED_FALSE = (
    ('full_archive_required', 'archivo completo necesario o no descartado'),
    ('granular_recovery_required', 'recuperación detallada necesaria o no descartada'),
    ('independent_verification_required', 'verificación independiente necesaria o no descartada'),
)


def select_persistence(facts: dict) -> dict:
    """Select compact only when every required fact is explicitly observed."""
    if not isinstance(facts, dict):
        return {'mode': 'full', 'reason': 'hechos de selección no disponibles'}
    for key, reason in _REQUIRED_TRUE:
        if facts.get(key) is not True:
            return {'mode': 'full', 'reason': reason}
    for key, reason in _REQUIRED_FALSE:
        if facts.get(key) is not False:
            return {'mode': 'full', 'reason': reason}
    count = facts.get('discovery_assignments')
    if type(count) is not int or count != 1:
        return {'mode': 'full', 'reason': 'se requiere una asignación de descubrimiento'}
    return {'mode': 'compact', 'reason': 'alcance acotado e inputs identificados sin obligaciones completas'}


def promotion_decision(selection: dict, observed_facts: dict) -> dict:
    """Escalate compact when new facts require it; never downgrade an acquired full mode."""
    if (not isinstance(selection, dict) or set(selection) != {'mode', 'reason'}
            or selection.get('mode') not in ('compact', 'full')
            or not isinstance(selection.get('reason'), str) or not selection['reason'].strip()):
        raise ValueError('persistence selection requires a known mode and reason')
    if selection['mode'] == 'full':
        return dict(selection)
    decision = select_persistence(observed_facts)
    return dict(selection) if decision['mode'] == 'compact' else decision
