"""NDC parsing: normalise to the canonical 5-4-2 (11 digit) format and pull NDCs out of free text."""
import re

# Hyphenated NDC-shaped token: labeler (4-5 digits), product (3-4), optional package (1-2).
# The lookarounds stop it matching inside longer digit/hyphen runs such as lot numbers.
_NDC_RE = re.compile(r"(?<![\d-])(\d{4,5})-(\d{3,4})(?:-(\d{1,2}))?(?![\d-])")
# A token directly after the word NDC is high confidence; bare tokens are only candidates.
_KEYWORD_RE = re.compile(r"NDC[^\d]{0,12}$", re.IGNORECASE)


def normalize_ndc(ndc: str) -> str | None:
    """Convert a hyphenated NDC to 11-digit 5-4-2 (or 9-digit 5-4 for a product NDC).

    The three FDA layouts (4-4-2, 5-3-2, 5-4-1) differ in which segment is short, so each
    segment is zero-padded to its canonical width. Returns None if it does not parse.
    """
    parts = ndc.strip().split("-")
    if not all(p.isdigit() for p in parts) or len(parts) not in (2, 3):
        return None
    widths = (5, 4, 2)
    if any(len(p) > w for p, w in zip(parts, widths)):
        return None
    return "".join(p.zfill(w) for p, w in zip(parts, widths))


def product_key(ndc: str) -> str | None:
    """Labeler + product segments only (9 digits); the level recalls usually cite."""
    full = normalize_ndc(ndc)
    return full[:9] if full else None


def extract_ndcs(text: str) -> list[tuple[str, bool]]:
    """Find NDC-shaped strings in free text.

    Returns (normalised NDC, preceded_by_NDC_keyword) pairs, de-duplicated in order of appearance.
    """
    seen, out = set(), []
    for m in _NDC_RE.finditer(text or ""):
        raw = "-".join(g for g in m.groups() if g)
        norm = normalize_ndc(raw)
        if norm and norm not in seen:
            seen.add(norm)
            out.append((norm, bool(_KEYWORD_RE.search(text[max(0, m.start() - 16) : m.start()]))))
    return out
