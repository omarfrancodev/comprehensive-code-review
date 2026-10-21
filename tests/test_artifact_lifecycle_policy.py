"""Documented start inputs execute correctly without telemetry or invented identity."""
import json
from pathlib import Path
import re
import unittest

import test_review_artifacts as fixtures

artifacts = fixtures.artifacts
ROOT = Path(__file__).resolve().parents[1]


class LifecyclePolicyTests(unittest.TestCase):
    setUp = fixtures.ArchiveTests.setUp
    git = fixtures.ArchiveTests.git
    write = fixtures.ArchiveTests.write
    prepare = fixtures.ArchiveTests.prepare
    read = fixtures.ArchiveTests.read
    retain = fixtures.ArchiveTests.retain

    def start_example(self):
        document = (ROOT / 'references/archive/lifecycle-trace.md').read_text(encoding='utf-8')
        example = re.search(r'## Start milestone example\s+.*?```json\s+(.*?)```', document, re.S)
        self.assertIsNotNone(example, 'operational start example is missing')
        return json.loads(example.group(1))

    def test_selective_loading_and_unknown_observations(self):
        skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        loading = skill.split('## Load by role', 1)[1].split('## Request options', 1)[0]
        self.assertIn('references/execution/worker-packets.md', loading)
        self.assertNotIn('references/maintenance/', loading)
        self.assertIn('`discovery/started`', skill)
        event = self.start_example()
        self.assertIsNone(event['occurred_at'])
        self.assertIsNone(event['actor']['provider_id'])
        self.assertIsNone(event['executor'])
        self.assertEqual(event['relations'], [])
        run = self.prepare()
        from recovery_fixtures import context10, record10
        manifest = self.read(run / 'cierre.json')
        context_record = record10('focused', 'automatic')
        context_record['scope'] = manifest['scope']
        context = context10(context_record)
        context['profile_history'] = manifest['profile_history']
        context['profile'] = manifest['profile_history'][-1]['profile']
        context['profile_reference'] = manifest['profile_history'][-1]['reference']
        context['review_inputs'] = manifest['review_inputs']
        artifacts.register(run, [], context_input=self.write('context.json', context))
        artifacts.record_event(run, self.write('start.json', event))
        self.assertEqual(artifacts.validate(run)['state'], 'processing')
        self.retain(run, unavailable_reason=None)
        artifacts.validate(run, require_retained=True)
        artifacts.close(run, cleanup='not_needed')
        self.assertEqual(artifacts.validate(run, require_retained=True)['state'], 'complete')
        self.assertFalse((run / 'measurements.json').exists())
        events = [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_bytes().splitlines()]
        started = next(e for e in events if e['kind'] == 'discovery' and e['status'] == 'started')
        self.assertIsNone(started['occurred_at'])
        self.assertEqual([e['kind'] for e in events][:4], ['prepare', 'profile', 'register', 'discovery'])
        self.assertEqual([e['kind'] for e in events][-2:], ['retain', 'close'])
