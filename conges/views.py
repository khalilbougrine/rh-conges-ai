import requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test

from .explain import explain_response_payload
from .forms import LeaveRequestForm
from .models import Employee, LeaveRequest


def is_staff(user):
    return user.is_staff


@login_required
def home_redirect(request):
    if request.user.is_staff:
        return redirect("history_admin")
    return redirect("my_history")


@login_required
def submit_leave_request(request):
    # ✅ Optionnel mais conseillé : seuls les employés (non staff) soumettent
    if request.user.is_staff:
        return redirect("history_admin")

    result = None
    error = None

    if request.method == "POST":
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            matricule = form.cleaned_data["matricule"]

            try:
                emp = Employee.objects.get(matricule=matricule)
            except Employee.DoesNotExist:
                emp = None

            if not emp:
                error = "Matricule introuvable."
            else:
                # ✅ Sécurité : un employé ne peut soumettre que pour SON matricule
                # (Si tu veux autoriser RH à soumettre, enlève cette condition)
                if hasattr(emp, "user_id") and emp.user_id and emp.user_id != request.user.id:
                    error = "Vous ne pouvez soumettre une demande que pour votre propre compte."
                else:
                    start = form.cleaned_data["start_date"]
                    end = form.cleaned_data["end_date"]
                    duration_days = (end - start).days + 1

                    if duration_days <= 0:
                        error = "Dates invalides."
                    else:
                        month = start.month

                        payload = {
                            "age": emp.age,
                            "gender": emp.gender,
                            "department": emp.department,
                            "job_title": emp.job_title,
                            "seniority_years": emp.seniority_years,
                            "contract_type": emp.contract_type,
                            "leave_balance": emp.leave_balance,
                            "duration_days": duration_days,
                            "leave_type": form.cleaned_data["leave_type"],
                            "leave_reason": form.cleaned_data["leave_reason"],
                            "month": month,
                            "is_peak_period": form.cleaned_data.get("is_peak_period") or 0,
                            "nb_previous_requests": emp.nb_previous_requests,
                            "nb_accepted_before": emp.nb_accepted_before,
                            "nb_refused_before": emp.nb_refused_before,
                            "team_size": emp.team_size,
                            "manager_approval": form.cleaned_data.get("manager_approval") or 0,
                            "overlapping_team_leaves": form.cleaned_data.get("overlapping_team_leaves") or 0,
                            "rules_violation_flag": form.cleaned_data.get("rules_violation_flag") or 0,
                        }

                        accepted = None
                        confidence = None
                        features_used = None
                        model_version = "rf_leave_v1"

                        try:
                            r = requests.post(
                                f"{settings.FASTAPI_BASE_URL}/predict",
                                json=payload,
                                timeout=5
                            )

                            r.raise_for_status()
                            data = r.json()

                            accepted = bool(data["accepted"])
                            confidence = float(data["confidence"])
                            features_used = data.get("features_used")
                            model_version = data.get("model_version", "rf_leave_v1")

                        except Exception as e:
                            error = f"Erreur appel IA: {e}"

                        # ✅ Sauvegarder en DB seulement si IA OK
                        if accepted is not None:
                            LeaveRequest.objects.create(
                                employee=emp,
                                start_date=start,
                                end_date=end,
                                duration_days=duration_days,
                                leave_type=payload["leave_type"],
                                leave_reason=payload["leave_reason"],
                                month=month,
                                is_peak_period=payload["is_peak_period"],
                                manager_approval=payload["manager_approval"],
                                overlapping_team_leaves=payload["overlapping_team_leaves"],
                                rules_violation_flag=payload["rules_violation_flag"],
                                accepted=accepted,
                                confidence=confidence,

                                # ✅ snapshot
                                raw_payload=payload,
                                features_sent=features_used,
                                model_version=model_version,

                                # ✅ statut
                                status=LeaveRequest.Status.PREDICTED,
                            )

                            result = {"accepted": accepted, "confidence": confidence}

        else:
            error = "Formulaire invalide."
    else:
        form = LeaveRequestForm()

    return render(request, "conges/submit.html", {"form": form, "result": result, "error": error})


@user_passes_test(is_staff)
def history_admin(request):
    records = []
    error = None

    if request.method == "POST":
        matricule = request.POST.get("matricule", "").strip()
        try:
            emp = Employee.objects.get(matricule=matricule)
            records = LeaveRequest.objects.filter(employee=emp).order_by("-created_at")
        except Employee.DoesNotExist:
            error = "Matricule introuvable."

    return render(request, "conges/history.html", {"records": records, "error": error})


@login_required
def my_history(request):
    try:
        emp = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        return render(request, "conges/my_history.html", {"error": "Aucun employé lié à ce compte."})

    records = LeaveRequest.objects.filter(employee=emp).order_by("-created_at")
    return render(request, "conges/my_history.html", {"records": records})


@user_passes_test(is_staff)
def validate_leave(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if request.method == "POST":
        leave.status = LeaveRequest.Status.VALIDATED
        leave.decided_by = request.user
        leave.decided_at = timezone.now()
        leave.hr_comment = request.POST.get("hr_comment", "")
        leave.save()
    return redirect("history_admin")


@user_passes_test(is_staff)
def reject_leave(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if request.method == "POST":
        leave.status = LeaveRequest.Status.REJECTED_BY_RH
        leave.decided_by = request.user
        leave.decided_at = timezone.now()
        leave.hr_comment = request.POST.get("hr_comment", "")
        leave.save()
    return redirect("history_admin")


@login_required
def explain_leave_request(request, leave_request_id: int):
    lr = get_object_or_404(LeaveRequest, id=leave_request_id)

    # ✅ RH (staff) peut voir tout
    # ✅ Employé peut voir seulement ses demandes
    if not request.user.is_staff:
        if lr.employee.user_id != request.user.id:
            return JsonResponse({"detail": "Forbidden"}, status=403)

    data = explain_response_payload(lr)
    return JsonResponse(data, status=200)




@login_required
def chat_leave(request, leave_id):
    lr = get_object_or_404(LeaveRequest, id=leave_id)

    # ✅ Sécurité : employé voit seulement ses demandes
    if not request.user.is_staff:
        if lr.employee.user_id != request.user.id:
            return render(request, "conges/chat_leave.html", {
                "lr": lr,
                "answer": "Accès refusé.",
                "sources": []
            }, status=403)

    answer = None
    sources = []

    if request.method == "POST":
        user_question = request.POST.get("question", "").strip()
        if not user_question:
            user_question = "Pourquoi ma demande a été refusée ?"

        payload = {
            "leave_request_id": lr.id,
            "question": user_question,
            "leave_type": getattr(lr, "leave_type", None),
            "tags": getattr(lr, "tags", None),
            "template_id": getattr(lr, "template_id", None),
            "top_k": 6
        }

        try:
            resp = requests.post(
                f"{settings.FASTAPI_BASE_URL}/decision/explain",
                json=payload,
                timeout=60
            )

            resp.raise_for_status()
            data = resp.json()
            answer = data.get("answer")
            sources = data.get("sources", [])
        except Exception as e:
            answer = f"Erreur lors de l'appel IA : {e}"

    return render(request, "conges/chat_leave.html", {
        "lr": lr,
        "answer": answer,
        "sources": sources
    })
