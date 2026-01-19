from pathlib import Path
from typing import List, Optional
import os

from fastapi import FastAPI
from pydantic import BaseModel

import pandas as pd
import joblib

from conges.rag.rag_chain import answer_rh_question

app = FastAPI(title="IA RH - Predict + RAG", version="1.0")

# =========================
# Paths
# =========================
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # racine rh_conges/
MODEL_DIR = Path(__file__).resolve().parent / "model"

MODEL_PATH = MODEL_DIR / "leave_prediction_model_v2.pkl"
FEATURES_PATH = MODEL_DIR / "feature_names_v2.pkl"

# =========================
# Load ML model
# =========================
model = joblib.load(MODEL_PATH)
feature_names = joblib.load(FEATURES_PATH)

# =========================
# Schemas
# =========================
class LeaveRequest(BaseModel):
    age: int
    gender: str
    department: str
    job_title: str
    seniority_years: float
    contract_type: str
    leave_balance: float
    duration_days: int
    leave_type: str
    leave_reason: str
    month: int
    is_peak_period: int
    nb_previous_requests: int
    nb_accepted_before: int
    nb_refused_before: int
    team_size: int
    manager_approval: int
    overlapping_team_leaves: int
    rules_violation_flag: int


class RagRequest(BaseModel):
    question: str
    leave_type: Optional[str] = None
    tags: Optional[List[str]] = None
    template_id: Optional[str] = None
    top_k: int = 6


class DecisionExplainRequest(BaseModel):
    leave_request_id: int
    question: str = "Pourquoi ma demande a été refusée ?"
    leave_type: Optional[str] = None
    tags: Optional[List[str]] = None
    template_id: Optional[str] = None
    top_k: int = 6


class RagResponse(BaseModel):
    answer: str
    sources: List[dict]
    allowed_sources: Optional[List[str]] = None


# =========================
# Health
# =========================
@app.get("/health")
def health():
    return {"status": "ok", "service": "predict + rag"}


# =========================
# ML Predict
# =========================
@app.post("/predict")
def predict(request: LeaveRequest):
    data = pd.DataFrame([request.dict()])

    # Feature engineering (comme ton ancienne API)
    data["balance_ratio"] = data["duration_days"] / (data["leave_balance"] + 1e-5)
    data["approval_rate_before"] = data["nb_accepted_before"] / (data["nb_previous_requests"] + 1e-5)
    data["is_low_balance_risk"] = (data["leave_balance"] < data["duration_days"]).astype(int)
    data["is_peak_and_overlapping"] = data["is_peak_period"] * data["overlapping_team_leaves"]
    data["is_maladie_low_balance"] = ((data["leave_type"] == "maladie") & (data["leave_balance"] < data["duration_days"])).astype(int)
    data["is_cdd_maladie"] = ((data["leave_type"] == "maladie") & (data["contract_type"] == "CDD")).astype(int)

    categorical_cols = ["gender", "department", "job_title", "contract_type", "leave_type", "leave_reason"]
    data_encoded = pd.get_dummies(data, columns=categorical_cols, drop_first=False)

    # align columns
    for col in feature_names:
        if col not in data_encoded.columns:
            data_encoded[col] = 0
    data_encoded = data_encoded[feature_names]

    features_used = {
        k: (round(float(v), 6) if isinstance(v, (float, int)) else v)
        for k, v in data_encoded.iloc[0].to_dict().items()
    }

    proba = model.predict_proba(data_encoded)[0][1]
    threshold = 0.38
    prediction = bool(proba >= threshold)

    return {
        "accepted": prediction,
        "confidence": round(float(proba), 3),
        "features_used": features_used,
        "model_version": "leave_prediction_model_v2",
        "threshold": threshold
    }


# =========================
# RAG endpoints
# =========================
@app.post("/rag/answer", response_model=RagResponse)
def rag_answer(payload: RagRequest):
    return answer_rh_question(
        project_root=PROJECT_ROOT,
        question=payload.question,
        leave_type=payload.leave_type,
        tags=payload.tags,
        template_id=payload.template_id,
        top_k=payload.top_k,
    )


@app.post("/decision/explain", response_model=RagResponse)
def decision_explain(payload: DecisionExplainRequest):
    return answer_rh_question(
        project_root=PROJECT_ROOT,
        question=payload.question,
        leave_type=payload.leave_type,
        tags=payload.tags,
        template_id=payload.template_id,
        top_k=payload.top_k,
    )
