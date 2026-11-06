"""Source spans for local paths in disclosure prose."""
import re

# One shared boundary for classification and for excluding filename substrings
# from URL recognition. A lone terminal backslash still belongs to the member.
_HOME_ROOT = r'''~[^~\s/\\;|<>()\]`'"]*[\\/]'''
_QUOTED_PATH = r'''(?P<quote>[`'"])(?P<quoted_path>(?:/|[A-Za-z]:[\\/]|\\\\|(?i:file:)|\[(?:ruta privada|referencia privada)\]|''' + _HOME_ROOT + r''')(?:\\(?:[\s\S]|$)|(?!(?P=quote))[^\\])*)(?:(?P<closing>(?P=quote))|$)'''
_POSIX_PATH = r'''(?<![\w:#/<])/(?!/)[^\s;|<>\)\]`'"]+'''
_LOCAL_PATH = r'''(?:(?<!\w)(?:[A-Za-z]:[\\/]|\\\\|//|file:)|(?:(?<!\S)|(?<=(?<!\S)[([{]))(?P<home_binding>[-\w]+[=:])''' + _HOME_ROOT + r'''|(?:(?<!\S)|(?<=(?<!\S)[([{=,:;]))''' + _HOME_ROOT + r''')[^\s;|<>\)\]`'"]*'''
_SOURCE_TOKENS = re.compile(_QUOTED_PATH + r'|(?P<url>https?://[^\s<>\)\]]+)|(?P<local>'
                            + _LOCAL_PATH + ')|' + _POSIX_PATH, re.IGNORECASE)


def source_tokens(value, url_spans):
    urls = iter(url_spans)
    url = next(urls, None)
    for match in _SOURCE_TOKENS.finditer(value):
        while url is not None and url[1] <= match.start():
            url = next(urls, None)
        if url is not None and url[0] <= match.start() < url[1]:
            if match.start() == url[0] and match['url'] is not None:
                yield match, url[1]
        else:
            yield match, match.end()


def _local_start(match):
    return match.end('home_binding') if match['home_binding'] else match.start()


def private_detail_path_spans(value, url_spans):
    """Treat a quoted private locator, including a historical path marker, as a unit."""
    for match, last in source_tokens(value, url_spans):
        if match['local'] is not None or match['quoted_path'] is not None:
            yield _local_start(match), last
