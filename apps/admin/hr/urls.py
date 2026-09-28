from django.urls import path

from . import views

app_name = "hr"
urlpatterns = [
    path("rh/funcionarios/", views.employee_list, name="employee_list"),
    path("rh/funcionarios/<uuid:pk>/", views.employee_detail, name="employee_detail"),
]
