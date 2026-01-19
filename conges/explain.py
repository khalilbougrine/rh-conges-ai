# conges/explain.py
from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple
from .rules_sources import sources_for_tags
from .normalizers import LeaveTypeNormalizer
from .models import LeaveRequest


# ---------------------------
# 1) Tags officiels V1
# ---------------------------
TAG_DURATION_LONG = "TAG_DURATION_LONG"
TAG_PEAK_PERIOD = "TAG_PEAK_PERIOD"
TAG_TEAM_OVERLAP = "TAG_TEAM_OVERLAP"
TAG_MANAGER_APPROVED = "TAG_MANAGER_APPROVED"
TAG_MANAGER_NOT_APPROVED = "TAG_MANAGER_NOT_APPROVED"
TAG_RULES_VIOLATION = "TAG_RULES_VIOLATION"
TAG_LOW_CONFIDENCE = "TAG_LOW_CONFIDENCE"
TAG_RH_OVERRIDE = "TAG_RH_OVERRIDE"

# Leave type tags (optionnel mais utile au retrieval)
TAG_LEAVE_TYPE_PREFIX = "TAG_LEAVE_TYPE_"
TAG_REASON_PROVIDED = "TAG_REASON_PROVIDED"


# ---------------------------
# 2) Templates officiels (IDs stables)
# ---------------------------
T_REFUS_SOLDE = "REFUS_SOLDE"
T_REFUS_PEAK = "REFUS_PEAK"
T_REFUS_OVERLAP = "REFUS_OVERLAP"
T_REFUS_TEAM_SMALL = "REFUS_TEAM_SMALL"         # (pas utilisé V1 car pas de team_size)
T_REFUS_RULE = "REFUS_RULE"
T_DISAGREEMENT = "RH_OVERRIDE"
T_VALIDATION_OK = "VALIDATION_OK"


# ---------------------------
# 3) ExplainContext (format canonique)
# ---------------------------
@dataclass
class ExplainContext:
    leave_request_id: int
    status: str
    final_decision: str
    ai_recommendation: Optional[bool]
    confidence: Optional[float]
    tags: List[str]
    leave_type: Optional[str]
    month: Optional[int]
    has_hr_decision: bool
    decided_by: Optional[str]
    decided_at: Optional[str]
    hr_comment: Optional[str]
    template_id: str


# ---------------------------
# 4) Helpers
# ---------------------------
def _safe_bool(val) -> Optional[bool]:
    if val is None:
        return None
    return bool(val)


def _has_hr_decision(lr: LeaveRequest) -> bool:
    return lr.status in (
        LeaveRequest.Status.VALIDATED,
        LeaveRequest.Status.REJECTED_BY_RH,
    )


def build_tags(lr: LeaveRequest) -> List[str]:
    tags: List[str] = []

    # Leave type tag
    normalized_leave_type = LeaveTypeNormalizer.normalize(lr.leave_type)
    if normalized_leave_type:
        tags.append(f"{TAG_LEAVE_TYPE_PREFIX}{normalized_leave_type}")

    # Reason provided
    if lr.leave_reason and str(lr.leave_reason).strip():
        tags.append(TAG_REASON_PROVIDED)

    # Peak period
    if int(lr.is_peak_period or 0) == 1:
        tags.append(TAG_PEAK_PERIOD)

    # Overlap in team
    if (lr.overlapping_team_leaves or 0) > 0:
        tags.append(TAG_TEAM_OVERLAP)

    # Manager approval
    if lr.manager_approval is not None:
        if int(lr.manager_approval) == 1:
            tags.append(TAG_MANAGER_APPROVED)
        else:
            tags.append(TAG_MANAGER_NOT_APPROVED)

    # Rules violation flag
    if int(lr.rules_violation_flag or 0) == 1:
        tags.append(TAG_RULES_VIOLATION)

    # Confidence tag (optional)
    if lr.confidence is not None and float(lr.confidence) < 0.55:
        tags.append(TAG_LOW_CONFIDENCE)

    # RH override tag (if HR decided opposite of AI)
    if _has_hr_decision(lr) and lr.accepted is not None:
        ai_rec = bool(lr.accepted)
        hr_final = (lr.status == LeaveRequest.Status.VALIDATED)
        if ai_rec != hr_final:
            tags.append(TAG_RH_OVERRIDE)

    return tags


def choose_template_id(lr: LeaveRequest, tags: List[str]) -> str:
    """
    Priorité de template (V1) :
    1) RH override -> RH_OVERRIDE
    2) Rules violation -> REFUS_RULE
    3) Overlap -> REFUS_OVERLAP
    4) Peak -> REFUS_PEAK
    5) Manager not approved -> REFUS_RULE (temporaire V1)
    6) Sinon, si décision finale VALIDATED -> VALIDATION_OK
    7) Sinon fallback -> REFUS_RULE (si refus) ou VALIDATION_OK
    """
    # 1) Désaccord RH / IA
    if TAG_RH_OVERRIDE in tags:
        return T_DISAGREEMENT

    # 2) Violations internes
    if TAG_RULES_VIOLATION in tags:
        return T_REFUS_RULE

    # 3) Overlap
    if TAG_TEAM_OVERLAP in tags:
        return T_REFUS_OVERLAP

    # 4) Peak
    if TAG_PEAK_PERIOD in tags:
        return T_REFUS_PEAK

    # 5) Manager defavorable
    if TAG_MANAGER_NOT_APPROVED in tags:
        return T_REFUS_RULE

    # 6) Si validé
    if lr.status == LeaveRequest.Status.VALIDATED:
        return T_VALIDATION_OK

    # 7) Fallback
    if lr.status == LeaveRequest.Status.REJECTED_BY_RH:
        return T_REFUS_RULE
    return T_VALIDATION_OK


def build_explain_context(lr: LeaveRequest) -> ExplainContext:
    tags = build_tags(lr)
    template_id = choose_template_id(lr, tags)

    has_hr = _has_hr_decision(lr)

    # ai_recommendation : ce que le modèle a recommandé (accepted = prediction)
    ai_rec = None if lr.accepted is None else bool(lr.accepted)

    ctx = ExplainContext(
        leave_request_id=lr.id,
        status=str(lr.status),
        final_decision=str(lr.status),
        ai_recommendation=ai_rec,
        confidence=float(lr.confidence) if lr.confidence is not None else None,
        tags=tags,
        leave_type=LeaveTypeNormalizer.normalize(lr.leave_type),
        month=int(lr.month) if lr.month is not None else None,
        has_hr_decision=has_hr,
        decided_by=str(lr.decided_by) if getattr(lr, "decided_by", None) else None,
        decided_at=str(lr.decided_at) if getattr(lr, "decided_at", None) else None,
        hr_comment=str(lr.hr_comment) if getattr(lr, "hr_comment", None) else None,
        template_id=template_id,
    )
    return ctx

from .templates_loader import get_template_text


def explain_response_payload(lr: LeaveRequest) -> dict:
    ctx = build_explain_context(lr)
    payload = asdict(ctx)

    payload["explanation"] = get_template_text(ctx.template_id)

    # ✅ sources = template + règles RH liées aux tags
    payload["sources"] = [
        {"doc": "explications_decisions.md", "template_id": ctx.template_id}
    ] + sources_for_tags(ctx.tags)

    return payload


