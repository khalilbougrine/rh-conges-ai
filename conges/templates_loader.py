# conges/templates_loader.py
import os
import re
from functools import lru_cache
from django.conf import settings

TEMPLATE_FILE = "explications_decisions.md"

TEMPLATE_MAP = {
    "REFUS_SOLDE": "Refus — Solde insuffisant",
    "REFUS_PEAK": "Refus — Période de pointe",
    "REFUS_OVERLAP": "Refus — Congés simultanés",
    "REFUS_TEAM_SMALL": "Refus — Équipe réduite",
    "REFUS_RULE": "Refus — Règle interne",
    "RH_OVERRIDE": "Désaccord RH / Système",
    "VALIDATION_OK": "Validation — Conditions remplies",
}


@lru_cache
def load_templates() -> dict:
    # ✅ source de vérité : settings.RG_KNOWLEDGE_DIR
    rg_dir = getattr(settings, "RG_KNOWLEDGE_DIR", None)
    if not rg_dir:
        raise RuntimeError("RG_KNOWLEDGE_DIR n'est pas défini dans settings.py")

    path = os.path.join(rg_dir, TEMPLATE_FILE)

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    templates = {}
    for template_id, title in TEMPLATE_MAP.items():
        pattern = rf"## {re.escape(title)}\n(.+?)(?=\n## |\Z)"
        match = re.search(pattern, content, re.S)
        if match:
            templates[template_id] = match.group(1).strip()

    return templates


def get_template_text(template_id: str) -> str:
    templates = load_templates()
    return templates.get(
        template_id,
        "Aucune explication standard n’est disponible pour cette décision."
    )
