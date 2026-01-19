from django.urls import path
from . import views
from .views import submit_leave_request, history_admin, my_history

urlpatterns = [
    path("", views.home_redirect, name="home_redirect"),  # 👈 NEW

    path("submit/", submit_leave_request, name="submit_leave"),
    path("history/", history_admin, name="history_admin"),
    path("my-history/", my_history, name="my_history"),

    path("<int:pk>/validate/", views.validate_leave, name="validate_leave"),
    path("<int:pk>/reject/", views.reject_leave, name="reject_leave"),

    path("explain/<int:leave_request_id>/", views.explain_leave_request, name="explain_leave"),
    path("chat/<int:leave_id>/", views.chat_leave, name="chat_leave"),
]
