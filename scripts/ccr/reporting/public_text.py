"""Typed source formatting for new public projections, before Markdown escaping."""
from ccr.reporting import markdown
from ccr.reporting.projections import publication_digest, public_sensitive_values
from ccr.contracts.check_disclosure import _legacy_safe_text


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
        identities.extend(row['id'] for row in record['checks'])
        identities.extend(row.get('review_id') for row in record.get('previous_reviews', []))
        for value in identities:
            if isinstance(value, str):
                self.projection.structural(value, 'public identity')

    def text(self, value):
        return self.projection.text(str(value))

    def markdown(self, value):
        return markdown.markdown_text(self.text(value))

    def command(self, value):
        return markdown.markdown_text(self.projection.text(value, omit_commands=False))

    def reference(self, value):
        return markdown.reference_text(self.text(value))

    def final(self, body):
        # Only known values and URL privacy remain: Markdown backslashes and
        # its labels cannot create new filesystem/credential authority.
        return _legacy_safe_text(body, self.projection.secrets, redact_paths=False,
                                 _redact_assignments=False)
