'Prepare, register, validate, retain and close durable review evidence (Python 3.10+).\n\nMeasurement inputs are an explicit caller assertion of disjoint executions. Duplicate\npaths and execution_id values are refused; semantic overlap is not detectable here.\nTemporary-path authority and ownership belong to the coordinator. This helper never\ndeletes registered resources and must not be used to infer disposal authority.\n'

import argparse
import json
import stat
import sys
from ccr.archive.checkpoints import CHECKPOINT_EVIDENCE_LIMIT, checkpoint
from ccr.archive.evidence import _input_object, select_preflight_sources
from ccr.archive.inspection import inspect_run
from ccr.archive.integrity import (CHECKPOINT_METADATA_LIMIT, PENDING_CONTEXT_LIMIT,
                                   _evidence_name, verify_files as _verify_files)
from ccr.archive.lifecycle import block, close, pause, prepare, record_event, register, resume, select_profile, validate
from ccr.archive.lookup import find_candidates, select_latest
from ccr.archive.reader import load_run as _load_run
from ccr.archive.resources import transfer_resources
from ccr.archive.retention import retain
from ccr.archive.restart import (_RestartCancellationUnavailable, abandon_restart,
                                  record_restart_refusal, recover, restart)
from ccr.shared.encoding import archive_bytes as _json_bytes
from ccr.shared.json_io import read_json
from ccr.shared.paths import safe_path
from ccr.contracts import preflight as review_preflight
from ccr.workflow import profiles as review_profiles

def preflight_run(run_dir, context_input, *, phase, input_file=None, evidence_inputs=None):
    """Read-only phase preflight over one explicit native archive and selected inputs."""
    try:
        run, manifest, _ = _load_run(run_dir)
        _verify_files(run, manifest)
        context = _input_object(context_input, 'execution context', max_bytes=PENDING_CONTEXT_LIMIT)
        sources = {'evidence/context.json': _json_bytes(context)}
        for raw in evidence_inputs or []:
            path = safe_path(raw)
            if not stat.S_ISREG(path.stat().st_mode):
                raise ValueError('selected preflight evidence must be a regular file')
            name = 'evidence/' + _evidence_name(path.name)
            if name in sources:
                raise ValueError('duplicate selected preflight evidence name: ' + name)
            sources[name] = path.read_bytes()
        record = read_json(input_file, max_bytes=CHECKPOINT_METADATA_LIMIT) if input_file else None
        if phase in {'register', 'discovery', 'retain'}:
            sources = select_preflight_sources(run, manifest, sources, context, record)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {'error': str(exc)}, 2
    result = review_preflight.validate_preflight(
        phase=phase, manifest=manifest, logical_scope=manifest.get('logical_scope'),
        selection=None, context=context, record=record, sources=sources)
    return result, 0 if result['ready'] else 1

def main(argv=None, *, prog=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('prepare')
    for name in ('repo', 'scope-file', 'skill-version', 'harness'):
        create.add_argument('--' + name, required=True)
    create.add_argument('--output-root')
    create.add_argument('--previous-run')
    create.add_argument('--temporary-path', action='append')
    create.add_argument('--logical-scope-input', help='Existing JSON {mode, selector} for module/feature or partial local scopes')
    create.add_argument('--profile-input', required=True,
                        help='Existing JSON selection captured before the new run is created')
    create.add_argument('--current-inputs', help='Existing JSON with scope, external source hashes and observed identities')
    create.add_argument('--controller-input',
                        help='Existing JSON {identity, source} for the coordinating context')
    create.add_argument('--harness-id', help='Declared canonical catalog ID; overrides session CCR_HARNESS_ID')
    create.add_argument('--harness-source-file', help='Existing JSON {kind: user|platform, reference: text}; requires --harness-id')
    resources = commands.add_parser('register', help='Register verified owned temporary paths before use')
    resources.add_argument('--run-dir', required=True)
    resources.add_argument('--temporary-path', action='append', required=True)
    resources.add_argument('--context-input', help='Existing neutral context JSON with executor provenance')
    resources.add_argument('--authority', help='Explicit user authority for adopting an existing legacy session')
    transfer = commands.add_parser('transfer-resources', help='Transfer explicitly selected claimed workspaces to a successor run')
    transfer.add_argument('--source-run', required=True)
    transfer.add_argument('--successor-run', required=True)
    transfer.add_argument('--resource-path', action='append', required=True)
    transfer.add_argument('--authority', required=True)
    transfer.add_argument('--controller-input', required=True)
    inspect = commands.add_parser('inspect', help='Read-only status/integrity inspection of one explicit review run')
    inspect.add_argument('--run-dir', required=True)
    inspect.add_argument('--current-inputs', help='Existing JSON {scope, sources} verified by the coordinator')
    preflight_command = commands.add_parser('preflight', help='Read-only phase-specific contract check before work or retention')
    preflight_command.add_argument('--run-dir', required=True)
    preflight_command.add_argument('--context-input', required=True)
    preflight_command.add_argument('--phase', required=True, choices=('register', 'discovery', 'retain'))
    preflight_command.add_argument('--input', help='Optional final review candidate for retain preflight')
    preflight_command.add_argument('--evidence-input', action='append',
                                   help='Explicit selected evidence source; repeat for each file')
    lookup = commands.add_parser('lookup', help='Find bounded prior-run candidates for one repository and scope')
    lookup.add_argument('--repo', required=True)
    lookup.add_argument('--scope-file', required=True)
    lookup.add_argument('--archive-root', help='Explicit archive root; defaults to ~/.comprehensive-code-review/reviews')
    lookup.add_argument('--current-inputs', help='Existing JSON with scope, source hashes and optional input identities')
    lookup.add_argument('--limit', type=int, default=20)
    lookup.add_argument('--cursor', help='Opaque continuation cursor returned by a previous lookup page')
    lookup.add_argument('--logical-scope-input', help='Existing JSON selector required for module/feature or partial local lookup')
    lookup.add_argument('--include-history', action='store_true', help='Include explicitly ported historical consultation packages')
    lookup.add_argument('--select', choices=('latest',), help='Explicitly select latest verified result; never shown automatically')
    pause_command = commands.add_parser('pause', help='Record an explicit user-directed review pause')
    pause_command.add_argument('--run-dir', required=True)
    pause_command.add_argument('--authority-input', required=True,
                               help='JSON string or {"authority": text} with explicit user direction')
    pause_command.add_argument('--reason', required=True)
    pause_command.add_argument('--phase', required=True, choices=sorted(review_profiles.PHASES))
    block_command = commands.add_parser('block', help='Record an observed review failure without inferring a crash')
    block_command.add_argument('--run-dir', required=True)
    block_command.add_argument('--source', required=True)
    block_command.add_argument('--reason', required=True)
    block_command.add_argument('--phase', required=True, choices=sorted(review_profiles.PHASES))
    resume_command = commands.add_parser('resume', help='Resume a verified unchanged archive after explicit authority')
    resume_command.add_argument('--run-dir', required=True)
    resume_command.add_argument('--controller-input', required=True)
    resume_command.add_argument('--authority-input', required=True)
    resume_command.add_argument('--current-inputs', required=True)
    recover_command = commands.add_parser('recover', help='Complete exact helper-owned transactions or return a plan')
    recover_command.add_argument('--run-dir', required=True)
    recover_command.add_argument('--controller-input', required=True)
    recover_command.add_argument('--authority-input', required=True)
    recover_command.add_argument('--current-inputs', required=True)
    restart_command = commands.add_parser('restart', help='Create a fresh linked archive-8 review run')
    restart_command.add_argument('--run-dir', required=True, help='Verified source review run')
    restart_command.add_argument('--profile-input', required=True)
    restart_command.add_argument('--controller-input', required=True)
    restart_command.add_argument('--authority-input', required=True)
    restart_command.add_argument('--current-inputs', required=True)
    restart_command.add_argument('--logical-scope-input', help='Existing JSON {mode, selector} when logical boundaries change')
    restart_command.add_argument('--harness', default='unknown', help='Harness observed for this restart invocation')
    restart_command.add_argument('--harness-id', help='Canonical current harness ID from the CCR catalog')
    restart_command.add_argument('--harness-source-input', help='JSON provenance for an explicit harness ID')
    restart_command.add_argument('--transfer-path', action='append',
                                 help='Explicit owned session path to transfer; repeat for every active claim')
    abandon = commands.add_parser('abandon-restart', help='Cancel an unprepared restart or an exact empty resource-blocked successor')
    abandon.add_argument('--run-dir', required=True)
    abandon.add_argument('--intent-input', required=True, help='Exact intent path returned by inspect; no archive scan')
    abandon.add_argument('--controller-input', required=True)
    abandon.add_argument('--authority-input', required=True)
    abandon.add_argument('--reason', required=True)
    refusal = commands.add_parser('record-restart-refusal', help='Record a phase-specific cancellation refusal; leave the exact restart pending')
    refusal.add_argument('--run-dir', required=True)
    refusal.add_argument('--intent-input', required=True)
    refusal.add_argument('--controller-input', required=True)
    refusal.add_argument('--authority-input', required=True)
    refusal.add_argument('--reason', required=True)
    select = commands.add_parser('select-profile', help='Atomically capture a profile transition before using it')
    select.add_argument('--run-dir', required=True)
    select.add_argument('--selection-input', required=True)
    gate = commands.add_parser('validate', help='Read-only ownership, layout and retained hash checks')
    gate.add_argument('--run-dir', required=True)
    gate.add_argument('--require-retained', action='store_true', help='Require complete retained evidence before cleanup')
    gate.add_argument('--require-complete', action='store_true', help='Read-only gate for retained result and completed observed cleanup')
    gate.add_argument('--record-checkpoint', action='store_true', help='Record a passed milestone in an open trace archive')
    trace = commands.add_parser('record-event', help='Coordinator records one bounded structured milestone')
    trace.add_argument('--run-dir', required=True)
    trace.add_argument('--event-file', required=True)
    trace.add_argument('--execution-metadata', help='Optional existing review_runner run.json; no timing or identity inference')
    pending = commands.add_parser('checkpoint', help='Preserve selected inputs/results provisionally without retaining a verdict')
    pending.add_argument('--run-dir', required=True)
    pending.add_argument('--context-input', required=True)
    pending.add_argument('--evidence-input', action='append')
    pending.add_argument('--input', help='Optional structurally final review JSON; source gates remain mandatory for promotion')
    pending.add_argument('--phase', required=True, choices=sorted(review_profiles.PHASES - {'prepare'}))
    pending.add_argument('--diagnostic-input', help='Optional JSON array or {gate_errors: [...]} of bounded observed gate errors')
    pending.add_argument('--max-evidence-bytes', type=int, default=CHECKPOINT_EVIDENCE_LIMIT,
                         help='Selected checkpoint evidence byte limit, from 0 to 67108864')
    keep = commands.add_parser('retain')
    keep.add_argument('--run-dir', required=True)
    keep.add_argument('--input', help='Final review JSON; omit only when promoting the archive-owned final checkpoint')
    keep.add_argument('--expected-schema', type=int, choices=range(1, 11), help='Require the caller-selected final contract before retention')
    keep.add_argument('--measurement-input', action='append')
    keep.add_argument('--unavailable-reason')
    keep.add_argument('--temporary-path', action='append')
    keep.add_argument('--evidence-input', action='append')
    keep.add_argument('--context-input', help='Existing neutral context JSON with executor provenance')
    keep.add_argument('--handoff', action='store_true', help='Retain a handoff generated from the canonical record')
    keep.add_argument('--handoff-context-input', help='Explicit handoff spec/plan references and pending decisions; requires --handoff')
    finish = commands.add_parser('close')
    finish.add_argument('--run-dir', required=True)
    observed = finish.add_mutually_exclusive_group(required=True)
    observed.add_argument('--cleanup-file')
    observed.add_argument('--cleanup', choices=('complete', 'not_needed', 'pending'),
                          help='Observed state without creating a post-cleanup temporary file')
    finish.add_argument('--residual', action='append', help='Exact registered remaining path; repeat with --cleanup pending')
    finish.add_argument('--released-claims-input',
                        help='Existing JSON list of exact durable cleanup receipts for inline close')
    args = parser.parse_args(argv)
    try:
        authority_input = None
        if getattr(args, 'authority_input', None):
            authority_input = read_json(args.authority_input)
            if isinstance(authority_input, dict) and set(authority_input) == {'authority'}:
                authority_input = authority_input['authority']
            if not isinstance(authority_input, str):
                raise ValueError('authority input must be a JSON string or an object with exactly the authority field')
        if args.command == 'prepare':
            source = read_json(args.harness_source_file) if args.harness_source_file else None
            if args.harness_source_file and (not isinstance(source, dict) or args.harness_id is None):
                raise ValueError('harness source file requires an object and an explicit --harness-id')
            result = {'run_dir': prepare(args.repo, args.scope_file, args.skill_version, args.harness,
                                         args.output_root, args.previous_run, args.temporary_path,
                                         profile_input=args.profile_input,
                                         controller=read_json(args.controller_input) if args.controller_input else None,
                                         harness_id=args.harness_id, harness_source=source,
                                         current_inputs=read_json(args.current_inputs) if args.current_inputs else None,
                                         logical_scope_input=read_json(args.logical_scope_input) if args.logical_scope_input else None)}
        elif args.command == 'checkpoint':
            diagnostic = read_json(args.diagnostic_input) if args.diagnostic_input else None
            if isinstance(diagnostic, dict) and set(diagnostic) == {'gate_errors'}:
                diagnostic = diagnostic['gate_errors']
            result = checkpoint(args.run_dir, context_input=args.context_input,
                                evidence_inputs=args.evidence_input, input_record=args.input,
                                phase=args.phase, gate_errors=diagnostic,
                                max_evidence_bytes=args.max_evidence_bytes)
        elif args.command == 'retain':
            result = retain(args.run_dir, args.input, args.measurement_input,
                            args.unavailable_reason, args.temporary_path, args.evidence_input, args.context_input, args.handoff, args.handoff_context_input,
                            expected_schema=args.expected_schema)
        elif args.command == 'register':
            result = register(args.run_dir, args.temporary_path, context_input=args.context_input,
                              authority=args.authority)
        elif args.command == 'transfer-resources':
            result = transfer_resources(args.source_run, args.successor_run, args.resource_path,
                                        authority=args.authority, controller=read_json(args.controller_input))
        elif args.command == 'inspect':
            current = read_json(args.current_inputs) if args.current_inputs else None
            result = inspect_run(args.run_dir, current_inputs=current)
        elif args.command == 'preflight':
            result, exit_code = preflight_run(
                args.run_dir, args.context_input, phase=args.phase,
                input_file=args.input, evidence_inputs=args.evidence_input)
            print(json.dumps(result, ensure_ascii=False, allow_nan=False))
            return exit_code
        elif args.command == 'lookup':
            current = read_json(args.current_inputs) if args.current_inputs else None
            requested_scope = read_json(args.scope_file)
            logical_input = read_json(args.logical_scope_input) if args.logical_scope_input else None
            if args.select == 'latest':
                if current is None:
                    raise ValueError('--select latest requires --current-inputs')
                result = select_latest(args.repo, requested_scope, archive_root=args.archive_root,
                    current_inputs=current, logical_scope_input=logical_input)
            else:
                result = find_candidates(args.repo, requested_scope,
                    archive_root=args.archive_root, limit=args.limit, cursor=args.cursor,
                    current_inputs=current, logical_scope_input=logical_input,
                    include_history=args.include_history)
        elif args.command == 'pause':
            result = pause(args.run_dir, authority=authority_input, reason=args.reason, phase=args.phase)
        elif args.command == 'block':
            result = block(args.run_dir, source=args.source, reason=args.reason, phase=args.phase)
        elif args.command == 'resume':
            result = resume(args.run_dir, controller=read_json(args.controller_input), authority=authority_input,
                            current_inputs=read_json(args.current_inputs))
        elif args.command == 'recover':
            result = recover(args.run_dir, controller=read_json(args.controller_input), authority=authority_input,
                             current_inputs=read_json(args.current_inputs))
        elif args.command == 'restart':
            harness_source = read_json(args.harness_source_input) if args.harness_source_input else None
            result = {'run_dir': restart(args.run_dir, profile_input=args.profile_input,
                         controller=read_json(args.controller_input), authority=authority_input,
                         current_inputs=read_json(args.current_inputs), transfer_paths=args.transfer_path,
                           logical_scope_input=read_json(args.logical_scope_input) if args.logical_scope_input else None,
                         harness={'harness': args.harness, 'harness_id': args.harness_id,
                                  'harness_source': harness_source})}
        elif args.command == 'abandon-restart':
            result = abandon_restart(args.run_dir, intent_path=args.intent_input,
                controller=read_json(args.controller_input), authority=authority_input, reason=args.reason)
        elif args.command == 'record-restart-refusal':
            result = record_restart_refusal(args.run_dir, intent_path=args.intent_input,
                controller=read_json(args.controller_input), authority=authority_input, reason=args.reason)
        elif args.command == 'select-profile':
            result = select_profile(args.run_dir, args.selection_input)
        elif args.command == 'validate':
            result = validate(args.run_dir, args.require_retained, args.record_checkpoint, require_complete=args.require_complete)
        elif args.command == 'record-event':
            result = record_event(args.run_dir, args.event_file, args.execution_metadata)
        else:
            receipts = read_json(args.released_claims_input) if args.released_claims_input else None
            if receipts is not None and not isinstance(receipts, list):
                raise ValueError('released claims input must be a JSON list')
            result = close(args.run_dir, args.cleanup_file, cleanup=args.cleanup,
                           residuals=args.residual, released_claims=receipts)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        detail = {'error': str(exc)}
        if isinstance(exc, _RestartCancellationUnavailable):
            detail['cancellation_denial'] = exc.diagnostic()
        print(json.dumps(detail, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
