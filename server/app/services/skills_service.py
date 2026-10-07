"""Read-only access to the curated skills gazetteer.

The gazetteer is the matching pipeline's vocabulary: ``diff_skills`` resolves a
job's ``requiredSkills`` against it, so a skill the gazetteer has never seen
scores differently from one it has. Exposing it lets the client's skill inputs
suggest exactly those canonical names instead of letting a candidate invent
"React 18" and silently lose a match on formatting.
"""

from .skills_gazetteer import SKILLS, extract_skills


def catalogue() -> list[dict]:
    """Every canonical skill with its sorted aliases, in stable name order."""
    return [
        {"name": name, "aliases": sorted(aliases)} for name, aliases in sorted(SKILLS.items())
    ]


def suggest(prefix: str, limit: int = 12) -> list[str]:
    """Canonical skills whose name or alias starts with ``prefix``.

    Used for type-ahead; the matcher is case-insensitive and matches on a
    normalized prefix so "rea" finds "React" and "py" finds "Python".
    """
    needle = (prefix or "").strip().lower()
    if not needle:
        return []
    hits: list[str] = []
    for name, aliases in SKILLS.items():
        if name.lower().startswith(needle) or any(
            alias.lower().startswith(needle) for alias in aliases
        ):
            hits.append(name)
    return sorted(hits)[:limit]


__all__ = ["catalogue", "extract_skills", "suggest"]
