# conges/rules_sources.py
from typing import List, Dict

# mapping tag -> sources RH (doc + section)
TAG_TO_SOURCES: Dict[str, List[dict]] = {
    "TAG_MANAGER_NOT_APPROVED": [
        {"doc": "politique_conges.md", "section": "Règle 9 — Refus en cas d’avis défavorable"}
    ],
    "TAG_MANAGER_APPROVED": [
        {"doc": "politique_conges.md", "section": "Règle 8 — Avis du manager"}
    ],
    "TAG_RULES_VIOLATION": [
        {"doc": "politique_conges.md", "section": "Règle 2 — Critères d’analyse"}
    ],
    "TAG_PEAK_PERIOD": [
        {"doc": "periodes_pointe.md", "section": "Impact sur les demandes de congés"}
    ],
    "TAG_TEAM_OVERLAP": [
        {"doc": "periodes_pointe.md", "section": "Congés simultanés dans l’équipe"}
    ],
}

def sources_for_tags(tags: List[str]) -> List[dict]:
    sources: List[dict] = []
    seen = set()

    for t in tags:
        for src in TAG_TO_SOURCES.get(t, []):
            key = (src["doc"], src.get("section"))
            if key not in seen:
                seen.add(key)
                sources.append(src)

    return sources
