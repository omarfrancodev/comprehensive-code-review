"""Canonical reference locations and navigable local Markdown links."""
from pathlib import Path
import hashlib
import json
import re
import unittest
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'workflow': ('scopes', 'profiles', 'capabilities', 'reading-strategy', 're-review', 'review-areas', 'reuse'),
    'dimensions': ('design-testability', 'contracts-data', 'security-operation'),
    'execution': ('reviewers', 'worker-packets', 'workspaces', 'external-cli'),
    'contracts': ('result-contract', 'identifiers', 'priority-calibration'),
    'archive': ('artifacts', 'lifecycle-trace', 'recovery', 'history'),
    'reporting': ('report-format', 'publication', 'delivery', 'handoff'),
    'maintenance': ('evaluation', 'measurements'),
}


class ReferenceLayoutTests(unittest.TestCase):
    def test_canonical_locations_and_local_links(self):
        expected = {group + '/' + name + '.md' for group, names in GROUPS.items() for name in names}
        actual = {p.relative_to(ROOT / 'references').as_posix() for p in (ROOT / 'references').rglob('*.md')}
        self.assertEqual(actual, expected)
        self.assertEqual(list((ROOT / 'references').glob('*.md')), [])
        documents = [ROOT / 'SKILL.md', ROOT / 'README.md']
        documents.extend((ROOT / 'references').rglob('*.md'))
        documents.extend((ROOT / 'docs').rglob('*.md'))
        snapshots = {ROOT / 'docs/validation/priority-calibration-evidence' / f'{kind}-instructions.md':
                     f'{kind}-manifest.json' for kind in ('baseline', 'candidate')}
        for source in documents:
            if source in snapshots:
                # These are immutable role-input bytes with links relative to their
                # original source, not independently navigable documentation.
                manifest = json.loads((source.parent / snapshots[source]).read_text(encoding='utf-8'))
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                                 manifest['instructions_sha256'])
                continue
            # Fenced examples describe inputs rather than links in the document.
            content = re.sub(r'```.*?```', '', source.read_text(encoding='utf-8'), flags=re.S)
            for destination in re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)', content):
                destination = destination.split('#', 1)[0].strip('<>')
                if not destination or re.match(r'[a-zA-Z][\w+.-]*:', destination):
                    continue
                with self.subTest(source=source.relative_to(ROOT), destination=destination):
                    self.assertTrue((source.parent / unquote(destination)).exists(), 'missing local link')
