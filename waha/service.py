import base64
import json
import logging
import time
import uuid

import httpx
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


def _waha_url(path):
    base = settings.WAHA_BASE_URL.rstrip('/')
    return f'{base}{path}'


def _waha_headers():
    headers = {'Content-Type': 'application/json'}
    api_key = getattr(settings, 'WAHA_API_KEY', '')
    if api_key:
        headers['X-Api-Key'] = api_key
    return headers


def create_session(tenant_id, request=None):
    from .models import WahaSession
    from tenants.models import Tenant

    tenant = Tenant.objects.get(pk=tenant_id)
    session_name = f'tenant_{tenant_id}_{uuid.uuid4().hex[:8]}'
    webhook_token = uuid.uuid4().hex

    webhook_url = None
    webhook_base = getattr(settings, 'WAHA_WEBHOOK_URL', '')
    if webhook_base:
        webhook_url = f'{webhook_base.rstrip("/")}{reverse("waha:webhook", kwargs={"token": webhook_token})}'
    elif request:
        webhook_url = request.build_absolute_uri(
            reverse('waha:webhook', kwargs={'token': webhook_token})
        )

    payload = {
        'name': session_name,
        'start': True,
    }
    if webhook_url:
        payload['webhooks'] = [{
            'url': webhook_url,
            'events': ['message', 'session.status'],
        }]

    try:
        resp = httpx.post(
            _waha_url('/api/sessions'),
            json=payload,
            headers=_waha_headers(),
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.exception(f"[WAHA API EXCEPTION] Failed to connect or create session for tenant {tenant_id}")
        return {'error': f'Falha ao criar sessão: {e}'}

    WahaSession.objects.update_or_create(
        tenant=tenant,
        defaults={
            'session_name': session_name,
            'webhook_token': webhook_token,
            'is_connected': False,
            'qr_code': '',
        },
    )

    for _ in range(6):
        qr = get_qr_code(session_name)
        if qr:
            break
        time.sleep(2)
    return {'success': True, 'session_name': session_name, 'qr_code': qr or ''}


def get_qr_code(session_name):
    try:
        resp = httpx.get(
            _waha_url(f'/api/{session_name}/auth/qr'),
            headers=_waha_headers(),
            timeout=10,
        )
        if resp.status_code == 200 and len(resp.content) > 100:
            return base64.b64encode(resp.content).decode()
    except Exception:
        pass
    return ''


def get_session_status(session_name):
    try:
        resp = httpx.get(
            _waha_url(f'/api/sessions/{session_name}'),
            headers=_waha_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        qr_b64 = ''
        qr_resp = httpx.get(
            _waha_url(f'/api/{session_name}/auth/qr'),
            headers=_waha_headers(),
            timeout=10,
        )
        if qr_resp.status_code == 200 and len(qr_resp.content) > 100:
            qr_b64 = base64.b64encode(qr_resp.content).decode()
        return {
            'status': data.get('status', 'UNKNOWN'),
            'qr_code': qr_b64,
        }
    except Exception:
        return {'status': 'ERROR', 'qr_code': ''}


def normalize_phone(number):
    number = number.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if number.startswith('+'):
        number = number[1:]
    if not number.startswith('55'):
        number = '55' + number
    if '@' not in number:
        number = f'{number}@c.us'
    return number


def send_whatsapp(session_name, to_number, message):
    try:
        resp = httpx.post(
            _waha_url(f'/api/send/{session_name}/messages'),
            json={
                'chatId': normalize_phone(to_number),
                'text': message,
            },
            headers=_waha_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return {'success': True}
    except Exception as e:
        return {'error': str(e)}


def delete_session(session_name):
    try:
        httpx.post(
            _waha_url(f'/api/sessions/{session_name}/logout'),
            headers=_waha_headers(),
            timeout=15,
        )
    except Exception:
        pass
    try:
        httpx.delete(
            _waha_url(f'/api/sessions/{session_name}'),
            headers=_waha_headers(),
            timeout=10,
        )
    except Exception:
        pass
    return True
