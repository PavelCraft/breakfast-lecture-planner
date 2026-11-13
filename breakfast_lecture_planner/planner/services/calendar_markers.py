"""Structured calendar metadata embedded as readable hashtags."""

import re

from bs4 import BeautifulSoup, NavigableString, Tag


CATEGORY_MARKERS = {
    "ekadashi": "#Ekadaši",
    "fast": "#Pasninkas",
    "holiday": "#Šventės",
    "saints": "#ŠventųjųDienos",
}
KARTIKA_START = "#KartikaPradžia"
KARTIKA_END = "#KartikaPabaiga"
MARKERS = {
    **CATEGORY_MARKERS,
    "kartika_start": KARTIKA_START,
    "kartika_end": KARTIKA_END,
}
CANONICAL_TYPES = {value.casefold(): kind for kind, value in MARKERS.items()}
LEGACY_MARKERS = {
    "ekadashi": "[Экадаши]",
    "fast": "[Пост]",
    "holiday": "[Праздник]",
    "saints": "[Дни святых]",
    "kartika_start": "[Картика: начало]",
    "kartika_end": "[Картика: конец]",
}
MARKER_TYPES = {
    value.casefold(): kind
    for kind, values in ((kind, (MARKERS[kind], LEGACY_MARKERS[kind])) for kind in MARKERS)
    for value in values
}
MARKER_PATTERN = re.compile(
    r"(?<![\w#])(?:"
    + "|".join(re.escape(value) for value in sorted(MARKER_TYPES, key=len, reverse=True))
    + r")(?!\w)",
    flags=re.IGNORECASE,
)
CANONICAL_PATTERN = re.compile(
    r"(?<![\w#])(?:"
    + "|".join(re.escape(value) for value in sorted(CANONICAL_TYPES, key=len, reverse=True))
    + r")(?!\w)",
    flags=re.IGNORECASE,
)


def marker_types_in_text(text):
    """Return known hashtags in their textual order, without duplicates."""
    result = []
    for match in MARKER_PATTERN.finditer(text or ""):
        kind = MARKER_TYPES[match.group(0).casefold()]
        if kind not in result:
            result.append(kind)
    return result


def _remove_marker_text(text):
    return re.sub(r"[ \t]{2,}", " ", CANONICAL_PATTERN.sub("", text or "")).strip()


def marker_type(tag):
    """Only a whole, standalone block is a marker, never prose containing it."""
    if not isinstance(tag, Tag) or tag.name not in {"p", "div"}:
        return None
    if tag.find(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6"]):
        return None
    text = " ".join(tag.get_text(" ", strip=True).split()).casefold()
    return MARKER_TYPES.get(text)


def markers_in_html(html):
    soup = BeautifulSoup(html or "", "html.parser")
    result = []
    for text in soup.find_all(string=True):
        for match in CANONICAL_PATTERN.finditer(str(text)):
            kind = CANONICAL_TYPES[match.group(0).casefold()]
            if kind not in result:
                result.append(kind)
        parent = text.parent
        if (kind := marker_type(parent)) and kind not in result:
            result.append(kind)
    return result


def categories_in_html(html):
    present = set(markers_in_html(html))
    return [key for key in CATEGORY_MARKERS if key in present]


def public_day_content(html):
    """Hashtags are public content and remain visible in the daily card."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in list(soup.find_all(True)):
        if marker_type(tag) and tag.get_text(" ", strip=True).startswith("["):
            tag.decompose()
    return str(soup)


def set_markers_in_html(html, kinds):
    """Replace all known markers and put canonical hashtags at the start."""
    ordered = [kind for kind in MARKERS if kind in set(kinds)]
    soup = BeautifulSoup(html or "", "html.parser")
    marker_containers = {
        text.find_parent(["p", "div"])
        for text in soup.find_all(string=True)
        if CANONICAL_PATTERN.search(str(text))
    }
    for tag in list(soup.find_all(True)):
        if marker_type(tag):
            tag.decompose()
    for text in list(soup.find_all(string=True)):
        replacement = _remove_marker_text(str(text))
        if replacement != str(text):
            text.replace_with(NavigableString(replacement))
    for tag in list(soup.select("span.mention")):
        if not tag.get_text(strip=True):
            tag.decompose()
    for tag in marker_containers:
        if tag and not tag.get_text(strip=True) and not tag.find(["img", "table", "hr"]):
            tag.decompose()
    for kind in reversed(ordered):
        marker = soup.new_tag("p")
        marker.string = MARKERS[kind]
        soup.insert(0, marker)
    return str(soup)


def set_inline_markers(tag, kinds):
    """Replace hashtags inside one dated calendar paragraph in place."""
    ordered = [kind for kind in MARKERS if kind in set(kinds)]
    for text in list(tag.find_all(string=True)):
        replacement = _remove_marker_text(str(text))
        if replacement != str(text):
            text.replace_with(NavigableString(replacement))
    for mention in list(tag.select("span.mention")):
        if not mention.get_text(strip=True):
            mention.decompose()
    if ordered:
        tag.append(NavigableString(" " + " ".join(MARKERS[kind] for kind in ordered)))


def decorated_main_content(html):
    """Keep markers visible to editors, but make long schedules scannable."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all(True):
        kind = marker_type(tag)
        if kind:
            tag["class"] = [*tag.get("class", []), "schedule-marker", f"schedule-marker--{kind}"]
    return str(soup)
