import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from ai import models
from ai.agent import SGEChatAgent, SGEAgent


logger = logging.getLogger(__name__)


@login_required(login_url='login')
def chat_view(request):
    conversations = (
        models.Conversation.objects
        .filter(user=request.user, tenant=request.tenant)
        .order_by('-updated_at')
    )
    active_id = request.GET.get('conv')
    if not active_id and conversations.exists():
        active_id = conversations.first().id
    messages = []
    if active_id:
        messages = (
            models.ChatMessage.objects
            .filter(conversation_id=active_id)
            .order_by('created_at')
        )
    return render(request, 'ia/chat.html', {
        'conversations': conversations,
        'active_conversation_id': int(active_id) if active_id else None,
        'messages': messages,
    })


@require_POST
@login_required(login_url='login')
def conversation_create(request):
    conv = models.Conversation.objects.create(
        user=request.user, tenant=request.tenant, title='Nova conversa',
    )
    return JsonResponse({'id': conv.id, 'title': conv.title})


@require_POST
@login_required(login_url='login')
def conversation_rename(request, conv_id):
    conv = get_object_or_404(models.Conversation, pk=conv_id, user=request.user, tenant=request.tenant)
    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalido.'}, status=400)
    title = (payload.get('title') or '').strip()
    if not title:
        return JsonResponse({'error': 'Titulo vazio.'}, status=400)
    conv.title = title[:200]
    conv.save(update_fields=['title'])
    return JsonResponse({'id': conv.id, 'title': conv.title})


@require_POST
@login_required(login_url='login')
def conversation_delete(request, conv_id):
    conv = get_object_or_404(models.Conversation, pk=conv_id, user=request.user)
    conv_id = conv.id
    conv.delete()
    return JsonResponse({'deleted': conv_id})


@login_required(login_url='login')
def conversation_messages(request, conv_id):
    conv = get_object_or_404(models.Conversation, pk=conv_id, user=request.user)
    messages = (
        models.ChatMessage.objects
        .filter(conversation=conv)
        .order_by('created_at')
        .values('id', 'role', 'content', 'created_at')
    )
    return JsonResponse({
        'conversation': conv.id,
        'title': conv.title,
        'messages': list(messages),
    })


@require_POST
@login_required(login_url='login')
def chat_send(request):
    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalido.'}, status=400)

    conv_id = payload.get('conversation_id')
    user_message = (payload.get('message') or '').strip()
    if not user_message:
        return JsonResponse({'error': 'Mensagem vazia.'}, status=400)
    if not conv_id:
        return JsonResponse({'error': 'Conversa nao especificada.'}, status=400)

    conv = get_object_or_404(models.Conversation, pk=conv_id, user=request.user, tenant=request.tenant)
    reply = SGEChatAgent(request.user).reply(conv, user_message)
    return JsonResponse({
        'reply': reply,
        'role': 'assistant',
        'conversation_id': conv.id,
        'conversation_title': conv.title,
    })


@require_POST
@login_required(login_url='login')
def message_regenerate(request, msg_id):
    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        payload = {}
    conv_id = payload.get('conversation_id')
    conv = get_object_or_404(models.Conversation, pk=conv_id, user=request.user)
    reply = SGEChatAgent(request.user).regenerate_from(conv, msg_id)
    return JsonResponse({'reply': reply, 'role': 'assistant'})


@require_POST
@login_required(login_url='login')
def message_edit(request, msg_id):
    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalido.'}, status=400)
    new_content = (payload.get('message') or '').strip()
    conv_id = payload.get('conversation_id')
    if not new_content:
        return JsonResponse({'error': 'Mensagem vazia.'}, status=400)
    conv = get_object_or_404(models.Conversation, pk=conv_id, user=request.user)
    reply = SGEChatAgent(request.user).edit_and_resend(conv, msg_id, new_content)
    return JsonResponse({'reply': reply, 'role': 'assistant'})


@require_POST
@login_required(login_url='login')
def ai_reload(request):
    SGEAgent(request.tenant).invoke()
    result = models.AIResult.objects.filter(tenant=request.tenant).first()
    return JsonResponse({'result': result.result if result else ''})


@login_required(login_url='login')
def ia_history(request):
    results = models.AIResult.objects.filter(tenant=request.tenant).order_by('-created_at')
    return render(request, 'ia/history.html', {'results': results})
