from django import forms

class LeaveRequestForm(forms.Form):
    matricule = forms.CharField(max_length=50)

    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    leave_type = forms.CharField(max_length=50)
    leave_reason = forms.CharField(max_length=120)

    # pour commencer simple: on laisse ces flags au choix (ou default)
    is_peak_period = forms.IntegerField(min_value=0, max_value=1, initial=0, required=False)
    manager_approval = forms.IntegerField(min_value=0, max_value=1, initial=0, required=False)
    overlapping_team_leaves = forms.IntegerField(min_value=0, max_value=1, initial=0, required=False)
    rules_violation_flag = forms.IntegerField(min_value=0, max_value=1, initial=0, required=False)
