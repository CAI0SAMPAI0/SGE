from django.urls import path

from . import views


app_name = 'tenants'

urlpatterns = [
    path('empresa/cadastro/', views.company_signup, name='company_signup'),
    path('convite/<str:token>/', views.employee_signup, name='employee_signup'),
    path('convidar-funcionario/', views.invite_employee, name='invite_employee'),
    path('convidar-funcionario/<int:invitation_id>/excluir/', views.delete_invitation, name='delete_invitation'),
]
