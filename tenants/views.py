import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Tenant, Invitation
from app.models import UserProfile


def company_signup(request):
    if request.method == 'POST':
        company_name = request.POST.get('company_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        if not company_name or not username or not email or not password:
            messages.error(request, 'Preencha todos os campos obrigatórios.')
            return redirect('tenants:company_signup')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Usuário já existe.')
            return redirect('tenants:company_signup')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email já cadastrado.')
            return redirect('tenants:company_signup')

        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name,
            is_staff=True,
        )
        tenant = Tenant.objects.create(name=company_name, owner=user)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.tenant = tenant
        profile.save()
        login(request, user)
        messages.success(request, f'Empresa "{company_name}" criada com sucesso!')
        return redirect('home')

    return render(request, 'tenants/company_signup.html')


def employee_signup(request, token):
    try:
        inv = Invitation.objects.get(token=token, accepted=False)
    except Invitation.DoesNotExist:
        return render(request, 'tenants/invalid_invite.html', status=404)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        if not username or not password:
            messages.error(request, 'Preencha usuário e senha.')
            return redirect('tenants:employee_signup', token=token)

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Usuário já existe.')
            return redirect('tenants:employee_signup', token=token)

        user = User.objects.create_user(
            username=username, email=inv.email, password=password,
            first_name=first_name, last_name=last_name,
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.tenant = inv.tenant
        profile.save()
        inv.accepted = True
        inv.save()
        login(request, user)
        messages.success(request, f'Bem-vindo à {inv.tenant.name}!')
        return redirect('home')

    return render(request, 'tenants/employee_signup.html', {'invitation': inv})


@login_required(login_url='login')
def invite_employee(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.tenant:
        messages.warning(request, 'Você não pertence a uma empresa. Crie uma empresa para convidar funcionários.')
        return redirect('tenants:company_signup')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        if not email:
            messages.error(request, 'Email é obrigatório.')
            return redirect('tenants:invite_employee')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Este email já está cadastrado.')
            return redirect('tenants:invite_employee')

        tenant = request.user.profile.tenant
        token = uuid.uuid4().hex

        inv, created = Invitation.objects.update_or_create(
            tenant=tenant,
            email=email,
            defaults={
                'phone': phone,
                'token': token,
                'invited_by': request.user,
                'accepted': False,
            },
        )

        invite_url = request.build_absolute_uri(f'/convite/{token}')
        sent_whatsapp = False

        # Envia WhatsApp se tiver telefone do convidado e sessão conectada
        if phone:
            try:
                from waha.models import WahaSession
                from waha.service import send_whatsapp
                session = WahaSession.objects.get(tenant=tenant, is_connected=True)
                whatsapp_msg = (
                    f'Olá! Você foi convidado(a) por {request.user.get_full_name() or request.user.username} '
                    f'para entrar na empresa "{tenant.name}".\n\n'
                    f'Clique no link para criar sua conta: {invite_url}'
                )
                result = send_whatsapp(session.session_name, phone, whatsapp_msg)
                sent_whatsapp = result.get('success', False)
            except WahaSession.DoesNotExist:
                pass
            except Exception:
                pass

        # Envia email
        try:
            subject = f'Convite para entrar em {tenant.name}'
            body = (
                f'Olá!\n\n'
                f'Você foi convidado(a) por {request.user.get_full_name() or request.user.username} '
                f'para entrar na empresa "{tenant.name}".\n\n'
                f'Clique no link abaixo para criar sua conta:\n{invite_url}\n\n'
                f'Atenciosamente,\nEquipe SGE'
            )
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email])
            if sent_whatsapp:
                messages.success(request, f'Convite enviado por WhatsApp e Email para {phone}.')
            else:
                messages.success(request, f'Convite enviado por Email para {email}.')
        except Exception:
            messages.success(request, f'Convite gerado! Link: {invite_url}')
            if sent_whatsapp:
                messages.info(request, 'Convite também enviado por WhatsApp.')

        return redirect('tenants:invite_employee')

    invitations = Invitation.objects.filter(
        tenant=request.user.profile.tenant,
    ).order_by('-created_at')
    return render(request, 'tenants/invite.html', {'invitations': invitations})


@require_POST
@login_required(login_url='login')
def delete_invitation(request, invitation_id):
    if not hasattr(request.user, 'profile') or not request.user.profile.tenant:
        return JsonResponse({'error': 'Sem empresa'}, status=400)

    inv = get_object_or_404(Invitation, pk=invitation_id, tenant=request.user.profile.tenant)
    inv.delete()
    messages.success(request, f'Convite de {inv.email} removido.')
    return redirect('tenants:invite_employee')
