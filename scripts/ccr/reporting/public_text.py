"""Typed source formatting for new public projections, before Markdown escaping."""
import re
from urllib.parse import quote

from ccr.reporting import markdown
from ccr.reporting.projections import publication_digest, public_sensitive_values
from ccr.contracts.check_disclosure import _secret_spellings, redact_projected_text, safe_text


class PublicText:
    def __init__(self, record, disclosure, sources, contexts=()):
        # Shared pure lexer: no archive/delivery IO dependency in rendering.
        from ccr.reporting.text_projection import _Projection
        self.projection = _Projection(record, {}, '', publication_digest(record),
            check_disclosure_context=disclosure, check_disclosure_sources=sources)
        self.projection.new_policy = True
        self.projection.secrets = public_sensitive_values(record, self.projection.disclosure, sources,
                                                        editorial_texts=(*contexts, disclosure))
        scope = record['scope']
        identities = [record.get('review_id'), scope.get('repository'), scope.get('base'),
                      scope.get('head'), scope.get('snapshot'), scope.get('target')]
        for person in [record['responsible'], *record.get('change_authors', [])]:
            identities.extend((person.get('name'), person.get('username')))
        identities.extend(row['id'] for row in record['findings'])
        for row in record['checks']:
            identities.extend((row['id'], row['revision']))
        identities.extend(row.get('review_id') for row in record.get('previous_reviews', []))
        for row in record['rereview']:
            identities.extend(row.get(key) for key in ('id', 'previous_review_id', 'previous_finding_id'))
            identities.extend(row.get('check_ids', []))
        for value in identities:
            if isinstance(value, str):
                self.projection.structural(value, 'public identity')

    def text(self, value):
        return self.projection.text(str(value))

    def markdown(self, value):
        return markdown.markdown_text(self.text(value))

    def proven(self, value):
        # Only disclosure_view supplies these typed, proof-checked fields.
        # Apply contextual privacy without treating their operands as prose.
        return markdown.markdown_text(self._redact_known(value))

    def reference(self, value):
        return markdown.reference_text(self.text(value))

    def finding_location(self, kind, location):
        if kind == 'code':
            path = location['path'].strip()
            normalized = path.strip("'\"`").strip().replace('\\', '/')
            if (normalized.startswith('/') or normalized == '~' or re.match(r'^~[^/]*/', normalized)
                    or '..' in normalized.split('/') or re.search(r'[:\x00-\x1f\x7f]', normalized)):
                path = '[ruta privada]'
            else:
                # A typed code location may have archive/ or evidence/ as
                # a repository folder rather than as a session resource.
                path = safe_text(path, self.projection.secrets, redact_paths=False)
            label = markdown.markdown_text(f"{path}:{location['line']}")
        else:
            label = self.markdown(location['section'])
        url = location['url']
        if not url or re.search(r'[\\\x00-\x20\x7f]', url) or not self.projection.public_url(url):
            return label
        destination = quote(url, safe='/:#?&=%-._~')
        # Validate the escaped destination too: raw Markdown delimiters can
        # truncate the URL inspected by the prose privacy policy.
        if not self.projection.public_url(destination):
            return label
        return f'[{label}]({destination})'

    def _redact_known(self, value):
        return redact_projected_text(value, _secret_spellings(self.projection.secrets))

    def final(self, body):
        # Markdown escapes and labels cannot create assignment authority.
        return self._redact_known(body)
