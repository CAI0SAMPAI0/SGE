import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import WahaSession
from .service import create_session, delete_session, get_qr_code, get_session_status, send_whatsapp


@login_required(login_url='login')
def waha_status(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.tenant:
        return JsonResponse({'error': 'Sem empresa'}, status=400)

    tenant = request.user.profile.tenant
    try:
        session = WahaSession.objects.get(tenant=tenant)
        info = get_session_status(session.session_name)
        api_status = info.get('status', 'UNKNOWN')
        is_connected = api_status == 'WORKING'
        if is_connected != session.is_connected:
            session.is_connected = is_connected
            session.qr_code = '' if is_connected else info.get('qr_code', '')
            session.save(update_fields=['is_connected', 'qr_code'])
        return JsonResponse({
            'is_connected': is_connected,
            'qr_code': info.get('qr_code', ''),
            'status': api_status,
            'session_name': session.session_name,
        })
    except WahaSession.DoesNotExist:
        return JsonResponse({'is_connected': False, 'qr_code': '', 'status': 'NO_SESSION'})


@require_POST
@login_required(login_url='login')
def waha_connect(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.tenant:
        return JsonResponse({'error': 'Sem empresa'}, status=400)

    try:
        tenant = request.user.profile.tenant
        existing = WahaSession.objects.filter(tenant=tenant).first()
        if existing:
            info = get_session_status(existing.session_name)
            if info.get('status') == 'WORKING':
                return JsonResponse({'success': True, 'session_name': existing.session_name, 'already_connected': True})
            delete_session(existing.session_name)
            existing.delete()
        result = create_session(tenant.id, request)
        if 'error' in result:
            return JsonResponse(result, status=500)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@require_POST
@login_required(login_url='login')
def waha_disconnect(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.tenant:
        return JsonResponse({'error': 'Sem empresa'}, status=400)

    tenant = request.user.profile.tenant
    try:
        session = WahaSession.objects.get(tenant=tenant)
        delete_session(session.session_name)
        session.delete()
    except WahaSession.DoesNotExist:
        pass

    return JsonResponse({'success': True})


@csrf_exempt
def waha_webhook(request, token):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        session = WahaSession.objects.get(webhook_token=token)
    except WahaSession.DoesNotExist:
        return JsonResponse({'error': 'Invalid token'}, status=404)

    try:
        data = json.loads(request.body)
        event = data.get('event', '')
        payload = data.get('payload', {}) or {}
        if event == 'session.status':
            status = payload.get('status', '')
            session.is_connected = status == 'WORKING'
            if not session.is_connected:
                session.qr_code = ''
            else:
                session.qr_code = ''
            session.save(update_fields=['is_connected', 'qr_code'])
        elif event == 'connection.upsert':
            session.is_connected = payload.get('status') == 'open'
            session.qr_code = ''
            session.save(update_fields=['is_connected', 'qr_code'])
    except (json.JSONDecodeError, KeyError):
        pass

    return JsonResponse({'ok': True})
