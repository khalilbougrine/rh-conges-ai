from django.db import models
from django.conf import settings
from django.contrib.auth.models import User


class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)

    matricule = models.CharField(max_length=50, unique=True)
    age = models.IntegerField()
    gender = models.CharField(max_length=20)
    department = models.CharField(max_length=100)
    job_title = models.CharField(max_length=120)
    seniority_years = models.FloatField()
    contract_type = models.CharField(max_length=50)
    leave_balance = models.FloatField()
    team_size = models.IntegerField()

    # stats historiques
    nb_previous_requests = models.IntegerField(default=0)
    nb_accepted_before = models.IntegerField(default=0)
    nb_refused_before = models.IntegerField(default=0)

    def __str__(self):
        return self.matricule


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PREDICTED = "PREDICTED", "Prédit par IA"
        VALIDATED = "VALIDATED", "Validé par RH"
        REJECTED_BY_RH = "REJECTED_BY_RH", "Refusé par RH"

    employee = models.ForeignKey("Employee", on_delete=models.CASCADE, related_name="leave_requests")

    # Demandes de congé
    start_date = models.DateField()
    end_date = models.DateField()
    duration_days = models.PositiveIntegerField()
    leave_type = models.CharField(max_length=50)
    leave_reason = models.TextField(blank=True, null=True)
    month = models.PositiveSmallIntegerField()

    # Période de pointe et approbation du manager
    is_peak_period = models.BooleanField(default=False)
    manager_approval = models.BooleanField(default=False)
    overlapping_team_leaves = models.BooleanField(default=False)
    rules_violation_flag = models.BooleanField(default=False)

    # Décision IA
    accepted = models.BooleanField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)

    # Informations supplémentaires
    model_version = models.CharField(max_length=50, default="rf_leave_v1")
    features_sent = models.JSONField(null=True, blank=True)
    raw_payload = models.JSONField(null=True, blank=True)

    # Nouveau : statut métier RH
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PREDICTED
    )

    # Optionnel mais très utile pour audit RH
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="decided_leave_requests"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    hr_comment = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)


