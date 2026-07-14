from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views


urlpatterns = [
    path('admin/', admin.site.urls),

    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('api/v1/', include('authentication.urls')),

    path('', include('tenants.urls')),

    path('', views.home, name='home'),

    path('perfil/', views.profile_edit, name='profile_edit'),
    path('configuracoes/', views.settings_view, name='settings'),
    path('configuracoes/tema/', views.save_theme, name='save_theme'),
    path('configuracoes/grupo/criar/', views.group_create, name='group_create'),
    path('configuracoes/grupo/<int:group_id>/editar/', views.group_edit, name='group_edit'),
    path('configuracoes/grupo/<int:group_id>/excluir/', views.group_delete, name='group_delete'),
    path('configuracoes/usuario/<int:user_id>/editar/', views.user_edit, name='user_edit'),

    path('importar/', views.data_import, name='data_import'),
    path('importar/confirmar/', views.data_import_confirm, name='data_import_confirm'),

    path('ia/', include('ai.urls')),
    path('', include('suppliers.urls')),
    path('', include('brands.urls')),
    path('', include('categories.urls')),
    path('', include('products.urls')),
    path('', include('inflows.urls')),
    path('', include('outflows.urls')),

]
