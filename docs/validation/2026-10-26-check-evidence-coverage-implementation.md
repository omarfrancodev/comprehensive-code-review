# Implementación de trazabilidad explícita de CCR

Base de implementación: main CCR 3.2.0 (`559fc5c`), integrado en el worktree `docs/explicit-dimensions-spec`. El usuario autorizó implementar el spec y plan el 26 de octubre de 2026. Los cambios permanecen en la rama; no se publicó una release ni se modificó el visor independiente.

## Resultado y alcance

Final 11 conserva propósito por check y 27 dimensiones; la captura nueva emite recibo 2. Las proyecciones muestran evidencias por origen y cobertura por elemento. Los comentarios usan contextos editoriales por digest/índice y draft 2. Archivo 8/layout 2, trace 1, packet 1, recibo de entrega 1 y criterios de severidad/veredicto/reutilización conservan sus versiones y significado. Finales 1–10 y recibos 1 permanecen históricos sin migración.

## Evidencia observada por tarea

Todas las ejecuciones usan Python 3.12 del runtime disponible, con `-B`, `tests` y `scripts` del worktree real en sys.path y CWD/TEMP corto para las fixtures Git de Windows. No se copiaron fuentes para ejecutar pruebas.

| Tarea | RED observado | GREEN observado |
|---|---|---|
| Dimensiones | Módulo ausente | 4 pruebas; omisión de cada ID, tipos hostiles y agregados |
| Propósito/captura | Propósito/request/recibo nuevos no soportados; CLI expuso encoding cp1252 | 16 pruebas de propósito y recibos; captura real, rechazo antes de proceso, binding exacto |
| Contratos | Final 11 y selector de merge no soportados | 47 casos originales + 4 casos corregidos/focalizados; perfiles, ejecución, source gates y CLI |
| Archivo/preflight | Schema 11 rechazado; preflight aceptaba candidato sin purpose | 94 casos de archive/checkpoints/atomic/source/reuse; 3 preflight frescos y 4 characterization |
| Bloques | Import de blocks ausente | 54 casos de rendering, contrato y áreas |
| Comentarios | Argumento/contexto nuevo no soportado | 175 casos de publicación, drafts, CLI, contratos históricos y characterization |
| Entregas | Purpose sin política portátil; handoff sin propósito | 68 casos de entrega, publicación y trazabilidad; fuente inmutable, rollback/destinos y privacidad |
| Instrucciones | 3 fallos de política: contrato/IDs/captura anteriores | 40 pruebas focalizadas de política, enlaces, arquitectura y CLI; suite completa en ejecución |

Los conteos son por ejecución y no deben sumarse como casos únicos. Se usan `unittest discover` y las mismas suites del plan mediante un adaptador nativo que registra salida y exit code. `git diff --check` se verifica al cierre.

La ejecución completa descubrió 949 IDs únicos. El primer proceso quedó interrumpido con 355 aprobados; no se le atribuye un exit code final. Un repro de `test_partial_clone_scalar_query_does_not_acquire_missing_blob` falló por `NtCreateDirectoryObject 0xC0000022` de Git/MSYS dentro del sandbox y pasó fuera de esa restricción. La reanudación ejecuta solo los 594 casos fallidos o pendientes y persiste el resultado de cada ID, con las mismas fuentes de producto. Tres escenarios de symlink requieren un privilegio Windows no disponible. Un escenario existente de recuperación recibió `WinError 5` en `workspaces.save` al reemplazar un manifiesto temporal; su reintento aislado pasó (1 prueba, 11.335 s, exit 0), sin modificar esa implementación. Se conserva el error original y no se afirma su causa más allá del acceso denegado observado.

Después de corregir el bootstrap de imports, se ejecutaron también directamente y por separado las suites nuevas de renderizado (4), comentarios (4), preflight (3) y contrato 11 (6): 17 aprobados. La política ampliada de productores pasó 3/3 con `python -B -m unittest discover -s tests -p test_review_traceability_policy.py -v`.

## Aplicación de la skill: baseline y contrato nuevo

Escenario sintético: reclamación de jobs, C001 aprobado, resultado `Exactly one claim accepted`, cancelación segura por inspección estática y dos flujos de cobertura. Antes de editar instrucciones, un contexto fresco eligió final 10, recibo 1 y `--expected-schema 10`, produjo `**Cobertura:** Job claim; Cancellation.` y persistió cero dimensiones. Explicación literal: “Current instructions explicitly say aspects add no final-record fields.” No incluyó propósito porque el contrato anterior carecía de ese campo. Es una carencia estructural del contrato, no una negativa del agente bajo presión. La corrección usa slots obligatorios y plantilla explícita, con pruebas de aplicación de referencia; no se inventan dimensiones/evidencia no inspeccionadas.

Después, otro contexto fresco encontró final 11/recibo 2/`--expected-schema 11`, enumeró los 27 IDs y la agregación, mantuvo dos elementos independientes de cobertura y se negó a completar propósito/evidencia no suministrados. Explicación literal: “Do not invent C002 for static inspection or infer C001’s original purpose from its command/output.” Identificó contextos editoriales por digest, draft 2 y preservación de draft 1/recibo 1 sin rerun. Es una prueba de recuperación/aplicación de instrucciones, no una medición de tasa de acierto del modelo ni un review de producto real.

## Criterios y ejemplos

| Criterio | Evidencia y límite |
|---|---|
| AC1 | test_review_dimensions y contract11 exigen 27 IDs, motivos y agregados; no acreditan la verdad de una inspección |
| AC2–AC3 | purpose antes de workspace/proceso; receipt2/check equality y preflight11; un nombre de comando no sustituye objetivo |
| AC4 | receipt1 y finales históricos siguen válidos; reuse mantiene revisión y referencia originales; no se genera un proceso para completar metadatos |
| AC5–AC6 | blocks conserva static/null y checks distintos aunque compartan salida; elimina solo duplicados exactos por origen y conserva deltas |
| AC7 | coverage_lines conserva orden/duplicados; contexto público exige todos los índices y digest correcto |
| AC8 | full/brief/handoff conservan propósito y listas; política portátil distingue prosa de identidad y no altera fuentes |
| AC9 | draft2 rerender exacto; source_mismatch/body_mismatch/stale_draft; CRLF solo remoto; CLI compara cuerpo canónico |
| AC10 | suite completa conserva admisión/reuso, perfil, dispatch, fuentes, archivo y recursos; juicio semántico del modelo no se demuestra con validación estructural |

Antes: evidencia concatenada `Resultado observado [C001]; Delta del caso [C001]; src/jobs.py:claim` y cobertura concatenada. Después (fragmento parcial):

```markdown
- **Evidencia:**
  - **[C001](#C001)** — Resultado en Validación.
    - Delta del caso
  - **Inspección estática** — src/jobs.py:claim

- **Propósito:** Verificar que una reclamación conserve una sola ejecución.
- **Resultado:** Resultado observado

- **Cobertura:**
  - Creación de jobs
  - Reintento de jobs
```

C002 con el mismo resultado sigue siendo otro origen. Dos observaciones estáticas distintas siguen independientes; no se crea un check ficticio. Un recibo 1 no acredita captura de propósito para ejecución local nueva 11; un check reutilizado conserva evidencia/revisión históricas y no necesita rerun por esta presentación. Un resumen editorial con otro estado/campo, índice duplicado/omitido o digest equivocado falla; un resumen textual formalmente válido pero semánticamente engañoso requiere revisión editorial y no puede detectarse por igualdad de hashes.

## Decisiones de ejecución

Se conserva debajo la lista exhaustiva de rulings del ledger y su costo si fueran incorrectos. La revisión fresca de toda la rama está pendiente del cierre de la suite. Los logs de trabajo son temporales; este documento conserva comandos, resultados y límites observados.

### Rulings del ledger

- Ruling: Git Bash helper launch failed with 0xc0000142; use a native Python equivalent for task briefs, BASE, logs and completion gates — preserves steps on this Windows host — cost if wrong: bookkeeping differs from bundled helper, not product behavior.
- Ruling: spec names reporting/evidence.py but plan calls the same pure block owner reporting/blocks.py; use blocks.py for evidence and coverage together — avoids two owners — cost if wrong: module name differs, interfaces unchanged.
- Task 2: Ruling: capture CLI emits UTF-8 because the Spanish purpose exposed a cp1252/UTF-8 mismatch in the existing CLI test; cost if wrong: stdout encoding changes to the package standard.
- Ruling: reuse the just-observed passing test log after a commit-only operation, rather than rerunning unchanged checks — developer instruction prevents redundant testing — cost if wrong: external environment changes after that run are not re-observed.
- Task 3: Ruling: update external capture request fixtures for the now-required purpose; the schema-10 archive test explicitly constructs its historical receipt-1 fixture from observed command/stream facts, while new receipt-2 binding is tested separately. Cost if wrong: historical fixture construction could mask a version interaction, covered by new 11 gates.
- Task 4: Ruling: schema-11 retain preflight now validates the final structure itself; a RED test showed ready=true with missing purpose. Legacy schemas keep their prior preflight behavior. Cost if wrong: new candidates may be rejected earlier, with explicit construction diagnostics.
- Task 4: Ruling: structural preflight issues use candidate.* fields so unchanged-input runs rebuild the candidate instead of restarting discovery; RED→GREEN covers continuation_decision. Cost if wrong: an invalid unretained candidate could be retried, never silently retained.
- Task 6: Ruling: extend the additional historical profile-name CLI test with explicit coverage context because the full public boundary applies to schema 7 too; cost if wrong: wider fixture adaptation, original source contract unchanged.
- Task 7: Ruling: existing public handoff tests now pass the same explicit coverage context as comments; required by shared public policy, source records unchanged. Cost if wrong: more caller fixture changes, no implied classification.
- Task 8: Ruling: shared owned_check_request fixture now declares purpose, exposed by script CLI architecture run; source checks and legacy fixtures retain their versions. Cost if wrong: fixture abstraction could hide a missing caller field, covered by explicit missing-purpose request tests.
- Task 8: Ruling: align the current producer sentence in profiles.md and archive command examples with final 11; a new policy assertion exposed conflicting instructions. Cost if wrong: one extra operational reference changes, historical versions/examples remain distinct.
- Task 8: Ruling: add explicit enable_package_imports bootstrap to new traceability tests after standalone discovery exposed ModuleNotFoundError hidden by the native adapter. Cost if wrong: test harness imports change; runtime implementation is unchanged and standalone checks supplement the running full suite.
- Task 8: Ruling: the full run was interrupted and sandboxed Git/MSYS partial clones fail with NtCreateDirectoryObject 0xC0000022; two exact failing scenarios pass outside the sandbox. Resume only failed/unrun discovered IDs, preserving prior observed passes and logging each result durably. Cost if wrong: environmental differences between suite segments; same sources and full discovered-ID coverage are verified explicitly.
- Task 8: Ruling: align identifiers.md with preallocated immutable receipt-bound check IDs, because its generic provisional-check instruction conflicted with the new capture flow. Cost if wrong: one extra identity reference changes; historical and unbound provisional IDs remain supported.
- Task 8: Ruling: overlap the one fresh whole-branch review with the long-running complete suite, committing finished docs/policy first while marking validation pending. No completion/merge-ready claim until both finish; runtime is frozen. Cost if wrong: the final validation-only evidence commit is outside the reviewer snapshot, with no product code omitted.
