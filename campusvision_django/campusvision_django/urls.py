"""
URL configuration for campusvision_django project.
"""
from django.contrib import admin
from django.urls import path, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from app import views
from app import api

urlpatterns = [
    path('admin/', admin.site.urls),

    # Autenticação
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),
    path('accounts/login/', views.login_view, name='account_login'),
    path('profile/', views.profile, name='profile'),

    # Painel Principal e Gerenciamento
    path('', views.index, name='index'),
    path('manager/', views.manager, name='manager'),
    path('manager/approved/', views.manager_approved, name='manager_approved'),
    path('manager/waiting/', views.manager_waiting, name='manager_waiting'),
    path('manager/denied/', views.manager_denied, name='manager_denied'),
    path('upload/', views.upload_file, name='upload'),
    path('edit/<id>/', views.edit, name='edit'),
    path('mod/', views.moderate, name='mod'),
    path('mod/post/', views.moderate_post, name='moderate_post'),
    path('messages/', views.messages_view, name='messages'),
    path('alerts/', views.alerts, name='alerts'),
    path('settings/', views.settings_view, name='settings'),
    path('usermanager/', views.usermanager, name='usermanager'),
    path('buses/', views.bus_manager, name='bus_manager'),
    path('configuration_equipment/', views.configuration_equipment, name='configuration_equipment'),
    path('status/', views.status, name='status'),

    # Telas de Exibição da TV (Feeds)
    path('feeds/<title>/', views.feeds, name='feeds'),
    path('feeds-vertical/<title>/', views.feeds_vertical, name='feeds_vertical'),
    path('feeds-video/<title>/', views.feeds_video, name='feeds_video'),

    # APIs JSON para atualização em tempo real
    path('api/feed/<feed_name>/', views.api_feed_data, name='api_feed_data'),
    path('api/slides/<feed>/', api.slides, name='api_slides'),
    path('api/messages/', api.messages, name='api_messages'),

    # Servir arquivos de uploads (vídeos e imagens) em produção e desenvolvimento
    re_path(r'^static/uploads/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
