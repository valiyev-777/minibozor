"""The description is HTML now, so two things have to happen on the way in.

§5.2 ·4 of the receiving brief asks for a rich text description, and says two
things about it that are the server's job and not the editor's:

*Sanitise on the way in.* The web editor's schema already forbids everything
the phone apps cannot draw — that is what makes the editor safe to type into.
It is not what makes the *column* safe. ``PATCH /admin/products/{id}`` takes
JSON from whoever holds an admin token, and a column whose contents the
Android and iOS apps render as markup is not a place to store a string nobody
checked. The editor's whitelist is a convenience; this one is the rule.

*Keep the plain text alongside it for search.* ``catalog.py`` matches a
shopper's needle against the description with a LIKE. Against HTML that is
wrong in both directions: a search for ``li`` matches every card that has a
bulleted list, and a phrase that happens to straddle a ``<strong>`` matches
nothing. Plain text beside the markup fixes both, and costs one column.

No new dependency — the whitelist is small enough that ``html.parser`` from
the standard library is the right size of tool.
"""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser

# Exactly what the editor can produce and the apps can draw: bold, italic, the
# two lists, one heading level, paragraphs and a line break. Adding one here
# means teaching `web/src/components/card-form/rich-text.tsx`, the Android
# renderer and the iOS renderer about it — which is the friction that keeps the
# three from drifting apart.
ALLOWED = frozenset({"p", "br", "strong", "b", "em", "i", "ul", "ol", "li", "h2"})

# Void elements among the allowed set. `<br>` closes itself; nothing else does.
VOID = frozenset({"br"})

# Blocks whose boundary is a word boundary. Without this, `plain()` renders
# "<li>Charm</li><li>Rezina</li>" as "CharmRezina" and the search misses both.
BLOCK = frozenset({"p", "ul", "ol", "li", "h2", "br"})

# Elements whose *contents* go with them. Every other unknown tag is unwrapped
# — "<table><td>Charm</td></table>" is somebody's prose in the wrong markup and
# the words are worth keeping. These two are not prose: dropping the tag and
# keeping the body turns a blocked `<script>` into the visible text `alert(1)`.
DROP_BODY = frozenset({"script", "style"})


class _Clean(HTMLParser):
    """Rebuild the document from the tags on the whitelist and nothing else.

    Attributes are dropped wholesale rather than filtered. There is no `style`,
    `class` or `href` the apps read, so an attribute that survives is at best
    dead weight and at worst an `onclick`; the safe list is empty.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.open: list[str] = []
        self.muted = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in DROP_BODY:
            self.muted += 1
            return
        if tag not in ALLOWED:
            return
        if tag in VOID:
            self.out.append("<br />")
            return
        self.out.append(f"<{tag}>")
        self.open.append(tag)

    def handle_startendtag(self, tag: str, attrs: object) -> None:
        if tag in VOID:
            self.out.append("<br />")

    def handle_endtag(self, tag: str) -> None:
        if tag in DROP_BODY:
            self.muted = max(0, self.muted - 1)
            return
        if tag not in ALLOWED or tag in VOID:
            return
        # Close back to the matching tag rather than trusting the stray. A
        # malformed document closes what it opened; it does not get to close
        # something it never opened.
        if tag not in self.open:
            return
        while self.open:
            last = self.open.pop()
            self.out.append(f"</{last}>")
            if last == tag:
                break

    def handle_data(self, data: str) -> None:
        if self.muted:
            return
        self.out.append(escape(data, quote=False))

    def result(self) -> str:
        while self.open:
            self.out.append(f"</{self.open.pop()}>")
        return "".join(self.out)


class _Plain(HTMLParser):
    """The same document with the markup taken off and the words kept apart."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.muted = 0

    def _gap(self) -> None:
        if self.out and self.out[-1] != " ":
            self.out.append(" ")

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in DROP_BODY:
            self.muted += 1
        if tag in BLOCK:
            self._gap()

    def handle_startendtag(self, tag: str, attrs: object) -> None:
        if tag in BLOCK:
            self._gap()

    def handle_endtag(self, tag: str) -> None:
        if tag in DROP_BODY:
            self.muted = max(0, self.muted - 1)
        if tag in BLOCK:
            self._gap()

    def handle_data(self, data: str) -> None:
        if self.muted:
            return
        self.out.append(data)


def clean(html: str) -> str:
    """The description as it may be stored: whitelisted tags, no attributes."""
    if not html:
        return ""
    parser = _Clean()
    parser.feed(html)
    parser.close()
    return parser.result()


def plain(html: str) -> str:
    """The same description as words, for the shopper's search to match on."""
    if not html:
        return ""
    parser = _Plain()
    parser.feed(html)
    parser.close()
    return " ".join("".join(parser.out).split())
