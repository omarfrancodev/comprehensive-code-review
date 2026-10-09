"""Canonical reference locations and navigable local Markdown links."""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'workflow': ('scopes', 'profiles', 'capabilities', 'reading-strategy', 're-review', 'review-areas'),
    'execution': ('reviewers', 'worker-packets', 'workspaces', 'external-cli'),
    'contracts': ('result-contract', 'identifiers'),
    'archive': ('artifacts', 'lifecycle-trace'),
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
        for source in documents:
            # Fenced examples describe inputs rather than links in the document.
            content = re.sub(r'```.*?```', '', source.read_text(encoding='utf-8'), flags=re.S)
            for destination in re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)', content):
                destination = destination.split('#', 1)[0].strip('<>')
                if not destination or re.match(r'[a-zA-Z][\w+.-]*:', destination):
                    continue
                with self.subTest(source=source.relative_to(ROOT), destination=destination):
                    self.assertTrue((source.parent / unquote(destination)).exists(), 'missing local link')
