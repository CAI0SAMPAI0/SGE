from django.urls import path

from . import views

app_name = 'waha'

urlpatterns = [
    path('api/waha/status/', views.waha_status, name='status'),
    path('api/waha/connect/', views.waha_connect, name='connect'),
    path('api/waha/disconnect/', views.waha_disconnect, name='disconnect'),
    path('api/waha/webhook/<str:token>/', views.waha_webhook, name='webhook'),
]
