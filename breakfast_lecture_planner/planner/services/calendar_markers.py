"""Structured calendar metadata embedded in editable schedule text."""

from bs4 import BeautifulSoup, Tag


CATEGORY_MARKERS = {
    "ekadashi": "[Экадаши]",
    "fast": "[Пост]",
    "holiday": "[Праздник]",
    "saints": "[Дни святых]",
}
KARTIKA_START = "[Картика: начало]"
KARTIKA_END = "[Картика: конец]"
MARKER_TYPES = {value.casefold(): key for key, value in CATEGORY_MARKERS.items()}
MARKER_TYPES[KARTIKA_START.casefold()] = "kartika_start"
MARKER_TYPES[KARTIKA_END.casefold()] = "kartika_end"


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
    return [kind for tag in soup.find_all(True) if (kind := marker_type(tag))]


def categories_in_html(html):
    present = set(markers_in_html(html))
    return [key for key in CATEGORY_MARKERS if key in present]


def public_day_content(html):
    """Remove editor-only markers from the public daily card."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in list(soup.find_all(True)):
        if marker_type(tag):
            tag.decompose()
    return str(soup)


def decorated_main_content(html):
    """Keep markers visible to editors, but make long schedules scannable."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all(True):
        kind = marker_type(tag)
        if kind:
            tag["class"] = [*tag.get("class", []), "schedule-marker", f"schedule-marker--{kind}"]
    return str(soup)
