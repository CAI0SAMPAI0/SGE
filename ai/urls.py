from django.urls import path

from . import views


app_name = 'ai'

urlpatterns = [
    path('chat/', views.chat_view, name='chat'),
    path('chat/send/', views.chat_send, name='chat_send'),
    path('chat/conversation/create/', views.conversation_create, name='conversation_create'),
    path('chat/conversation/<int:conv_id>/messages/', views.conversation_messages, name='conversation_messages'),
    path('chat/conversation/<int:conv_id>/rename/', views.conversation_rename, name='conversation_rename'),
    path('chat/conversation/<int:conv_id>/delete/', views.conversation_delete, name='conversation_delete'),
    path('chat/message/<int:msg_id>/regenerate/', views.message_regenerate, name='message_regenerate'),
    path('chat/message/<int:msg_id>/edit/', views.message_edit, name='message_edit'),
    path('reload/', views.ai_reload, name='ai_reload'),
    path('historico/', views.ia_history, name='ia_history'),
]
