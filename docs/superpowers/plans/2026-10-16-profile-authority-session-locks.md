# Profile Authority and Session Locks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution. Steps use checkbox syntax; user-authorized chat fallback tracks delivery after commit.

**Goal:** corregir F058–F060 sin ampliar rollback ni publicar 2.12.0.

**Architecture:** validar continuidad de autoridad en la transición existente; endurecer apertura de locks y reutilizarlos por sesión durante registro, transferencia y cleanup. No cambiar formatos persistidos.

**Tech Stack:** Python 3.10+, unittest, subprocess, ctypes Windows, os/fcntl POSIX, Markdown, Git/GitHub.

**Spec:** [diseño](../specs/2026-10-16-profile-authority-session-locks-design.md).

## Global Constraints

- Python 3.10+, biblioteca estándar, sin servicios/dependencias nuevos.
- Archive 7/final 10 y 2.12.0 pendiente permanecen.
- No rollback F050/F052, merge, release ni cambios a reviews reales.
- No escribir/bloquear targets ajenos; no comprometer dos claims propios de una sesión.

## Review Focus

- Selección automática del mismo perfil después de explícita: rechazo también en historias ya construidas y gates finales.
- Sidecar guardado antes de fila: conservar replay/adopción parcial sin relajar identidad.
- Conflicto entre registro y cleanup bootstrap: no borrar una sesión adquirida por otra operación.
- Enlace sustituido entre precheck y open: el descriptor debe rechazarlo antes de escribir.
- Cancelación por BaseException y múltiples sesiones: liberar locks y conservar orden/reentrancia.

### Task 1: autoridad explícita continua (F058)

**Files:** scripts/review_profiles.py; tests/test_review_authority_and_claim_safety.py.
**Interfaces:** validate_selection(raw, previous=None) -> dict; validate_history(history) -> list[str]; select_profile(run_dir, selection_input) sin cambio de firma.

- [x] Añadir test de historia explicit/deep, automatic/deep, automatic/focused; exigir error y rechazo del final focused con esa historia. Añadir rechazo de select_profile sin cambiar snapshot y sustitución explícita autorizada válida.
- [x] Ejecutar tests -k authority en RED; mover la protección explícita fuera del cambio de nombre de perfil.
- [x] Ejecutar GREEN y tests de perfiles existentes.

### Task 2: apertura segura de lock (F060)

**Files:** scripts/review_run_lock.py; tests/test_review_lock_file_safety.py.
**Interfaces:** _open_lock_file(lock_path: Path) -> BinaryIO; run_locks(run_dirs) conserva API.

- [x] Probar enlace final a target vacío y sustitución tras _lock_identity, con target intacto y rechazo. Añadir hardlink real y excepción/liberación normal.
- [x] Observar RED. Implementar no-follow nativo Windows/POSIX, regularidad, atributos e identidad del descriptor antes de escribir.
- [x] Ejecutar GREEN y test_review_run_lock.py; anotar cualquier omisión por privilegios.

### Task 3: commit exclusivo por sesión (F059)

**Files:** scripts/review_resource_claims.py; scripts/review_artifacts.py; scripts/review_workspace.py; tests/test_review_authority_and_claim_safety.py.
**Interfaces:** session_claim_locks(paths) -> context manager; register y transfer_resources mantienen firmas; cleanup mantiene CLI.

- [x] Reproducción con dos procesos reales: A espera en atomic_write del sidecar tras digest; B intenta lo mismo; liberar A y luego B. Exigir único ganador A, verify_claim(A) válido y B sin filas/escrituras de archivo.
- [x] Observar RED. Añadir locks de sesiones existentes verificables al registro completo, transferencia completa y cleanup completo; conservar missing_unclaimed y recursos que no sean workspaces.
- [x] Probar conflicto durante transferencia/cleanup, orden múltiple, liberación por BaseException y replay de adopción parcial. Ejecutar GREEN focal.

### Task 4: revisión, suite y entrega

**Files:** references/archive/recovery.md; CHANGELOG.md; docs/validation/2026-10-16-profile-authority-session-locks.md; spec/plan actuales.

- [x] Revisión independiente estática acotada al delta; corregir defectos confirmados con RED/GREEN.
- [x] Ejecutar python -B -m unittest discover -s tests -v (con tempdir del workspace en este sandbox); reportar todos los fallos/omisiones. AST, enlaces y git diff --check.
- [ ] Registrar resultados, límites y checks de tareas. Commit descriptivo y push al PR 19; actualizar descripción y verificar SHA/árbol limpio en el chat.

## Self-review

Los tres hallazgos tienen reproducción, implementación y verificación. La exclusión por sesión incluye los mutadores que afectan ownership o eliminan sesiones; retain solo verifica claims existentes. Los locks no se borran al soltar para evitar dos inodos de coordinación. Los permisos de enlaces se reportan sin sustituir una omisión por una prueba simulada. El usuario autorizó ejecución nativa y actualización de este PR; no se solicita otra aprobación para estas correcciones.

## Execution ledger

- Ruling: raíz de coordinación de sesiones en git-common-dir/ccr-session-locks — la prueba real de baseline reprodujo contaminación por archivos hermanos de la sesión; una raíz Git verificada conserva estado y supervivencia al cleanup. Coste: un git rev-parse por checkout distinto, con caché dentro de cada invocación.
- Ruling: bloquear el inventario fusionado del manifiesto — una segunda carrera real reprodujo doble propietario con rutas predeclaradas y register([]); los argumentos nuevos solos no definen todo lo que se adquiere.
- RED inicial: autoridad y registro concurrente fallan como se esperaba; symlinks omitidos por WinError 1314 y hardlink bloqueado por sandbox. Fuera del sandbox, hardlink reproduce adquisición insegura.
- GREEN focal: 14 pruebas en 47.462 s; 12 aprobadas, 2 omitidas por privilegio de symlink. 25 pruebas de perfiles existentes y 3 de locks existentes también aprobadas. Suite completa y revisión independiente registradas en el cierre de este ledger.

- La revisión estática reprodujo rechazo de sesiones de varios worktrees; se agrupan por directorio Git común con ExitStack. Se añadieron registros de sesiones desde dos worktrees y desde dos clones con el mismo origin. La relectura no encontró un defecto residual concreto.
- GREEN focal definitivo: 16 pruebas en 69.658 s, 14 aprobadas y 2 omitidas por privilegio de symlink. Incluye registro concurrente explícito/predeclarado, baseline, transferencia, cleanup y sesiones de varios checkouts. Resultado completo registrado debajo.

- La primera suite completa (551, 2208.969 s) detectó un OSError convertido indebidamente por el wrapper cleanup; se conserva su propagación original. El test de recuperación tras borrado pasó después (15.757 s). La repetición completa usa tres grupos disjuntos de módulos, con comprobación de inventario/ausencia de duplicados. No se cuentan tandas preliminares como aprobadas.

## Resultado final

Suite completa repetida en grupos disjuntos: 184/184/183 pruebas en 1637.033/768.859/414.940 s, respectivamente. Unión comprobada de 551 IDs únicos: 548 aprobadas, tres omitidas por privilegio de symlink, cero fallos/errores; exit 0 en cada proceso. Pasaron ambas matrices extensas. Controles estáticos de siete Python y seis documentos aprobados. La [validación](../../validation/2026-10-16-profile-authority-session-locks.md) conserva el fallo inicial y su corrección.

La entrega se verifica en el chat después del commit/push y actualización del PR; ese paso no se marca anticipadamente dentro del propio commit. Se mantiene el worktree y no se ejecutan merge ni release.
