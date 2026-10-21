"""Shared schema enums and ordered validation diagnostics."""
from ccr.contracts.scope import MODES

STATES = {'candidate', 'confirmed', 'rejected', 'unresolved'}
VERDICTS = {
    'approvable': 'APROBABLE',
    'approvable_with_reservations': 'APROBABLE CON RESERVAS',
    'not_approvable': 'NO APROBABLE',
    'insufficient_evidence': 'EVIDENCIA INSUFICIENTE',
}
PRIORITIES = {'P0': '🔴 P0 — Crítico', 'P1': '🟠 P1 — Alto',
              'P2': '🟡 P2 — Importante', 'P3': '🔵 P3 — Menor'}
DESCRIPTION = {'aligned': 'coherente', 'needs_update': 'requiere actualización',
               'unverified': 'sin verificar', 'not_applicable': 'no aplica'}
VERIFICATION = {'independent': 'independiente', 'same_session': 'misma sesión',
                'skipped': 'omitida según perfil', 'unavailable': 'no disponible'}
ORIGINS = {'introduced': 'introducido', 'preexisting': 'preexistente', 'unknown': 'desconocido'}
CHECK_STATUS = {'passed': 'aprobada', 'failed': 'falló', 'blocked': 'bloqueada', 'not_run': 'no ejecutada'}
FAILURE_KINDS = {'product': 'producto', 'fixture': 'fixture', 'environment': 'entorno'}
PROFILES = {'economy': 'económico', 'balanced': 'equilibrado',
            'focused': 'focused (enfocado)', 'standard': 'standard (estándar)',
            'deep': 'profundo', 'extended': 'extendido'}
CURRENT_PROFILES = {'focused', 'standard', 'deep', 'extended'}
PROFILE_ALIASES = {'economy': 'focused', 'balanced': 'standard'}
PROFILE_PHASES = {'prepare': 'preparación', 'discovery': 'descubrimiento',
                  'verification': 'verificación', 'report': 'informe',
                  'retain': 'retención', 'cleanup': 'limpieza', 'close': 'cierre'}
MODE_LABELS = {'pr': 'PR', 'mr': 'MR', 'commit': 'commit', 'range': 'rango de commits',
               'staged': 'cambios preparados', 'unstaged': 'cambios sin preparar',
               'working': 'cambios locales', 'module': 'módulo',
               'feature': 'implementación de funcionalidad'}
REREVIEW_STATUS = {'resolved': 'resuelto', 'still_valid': 'vigente', 'withdrawn': 'retirado', 'new': 'nuevo'}
REREVIEW_STATUS['not_reevaluated'] = 'no reevaluado'
AREAS = {'A': 'Arquitectura y diseño', 'B': 'Comportamiento y negocio',
         'C': 'Contratos e integración', 'D': 'Datos y persistencia',
         'E': 'Seguridad y operación'}
AREA_STATUS = {'covered': 'Cubierta', 'partial': 'Parcial',
               'not_evaluated': 'No evaluada', 'not_applicable': 'No aplica'}
REVIEW_KINDS = {'review': 'Code Review', 'rereview': 'Re-review',
                'complement': 'Complement Code Review'}

class ValidationState:
    """Accumulate diagnostics while keeping validators small and consistent."""
    def __init__(self):
        self.errors = []
    def error(self, path, message):
        self.errors.append(f'{path}: {message}')
    def fields(self, value, names, path):
        if not isinstance(value, dict):
            self.error(path, 'expected object')
            return {}
        for name in names:
            if name not in value:
                self.error(f'{path}.{name}', 'required field missing')
        for name in value:
            if name not in names:
                self.error(f'{path}.{name}', 'unknown field')
        return value
    def array(self, value, path):
        if not isinstance(value, list):
            self.error(path, 'expected array')
            return []
        return value
    def text(self, value, path, nullable=False, empty=False):
        if nullable and value is None:
            return
        if not isinstance(value, str) or (not empty and not value.strip()):
            self.error(path, 'expected nonempty text' if not empty else 'expected text')
    def boolean(self, value, path):
        if type(value) is not bool:
            self.error(path, 'expected boolean')
    def enum(self, value, choices, path):
        if not isinstance(value, str) or value not in choices:
            self.error(path, 'invalid value')
