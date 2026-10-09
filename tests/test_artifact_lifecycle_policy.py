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
        artifacts.record_event(run, self.write('start.json', event))
        self.assertEqual(artifacts.validate(run)['state'], 'processing')
        artifacts.retain(run, self.final)
        artifacts.validate(run, require_retained=True)
        artifacts.close(run, cleanup='not_needed')
        self.assertEqual(artifacts.validate(run, require_retained=True)['state'], 'complete')
        self.assertFalse((run / 'measurements.json').exists())
        events = [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_bytes().splitlines()]
        self.assertIsNone(events[1]['occurred_at'])
        self.assertEqual([e['kind'] for e in events], ['prepare', 'discovery', 'retain', 'close'])
