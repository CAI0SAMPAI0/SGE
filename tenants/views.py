import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.utils import timezone

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
            messages.error(request, 'Preencha todos os campos obrigatorios.')
            return redirect('company_signup')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Usuario ja existe.')
            return redirect('company_signup')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email ja cadastrado.')
            return redirect('company_signup')

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
            messages.error(request, 'Preencha usuario e senha.')
            return redirect('employee_signup', token=token)

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Usuario ja existe.')
            return redirect('employee_signup', token=token)

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
        messages.success(request, f'Bem-vindo a {inv.tenant.name}!')
        return redirect('home')

    return render(request, 'tenants/employee_signup.html', {'invitation': inv})


@login_required(login_url='login')
def invite_employee(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.tenant:
        messages.error(request, 'Voce nao pertence a uma empresa.')
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, 'Email obrigatorio.')
            return redirect('invite_employee')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Este email ja esta cadastrado.')
            return redirect('invite_employee')

        token = uuid.uuid4().hex
        Invitation.objects.create(
            tenant=request.user.profile.tenant,
            email=email,
            token=token,
            invited_by=request.user,
        )
        messages.success(request, f'Convite enviado para {email}. Link: /convite/{token}')
        return redirect('invite_employee')

    invitations = Invitation.objects.filter(
        tenant=request.user.profile.tenant,
    ).order_by('-created_at')
    return render(request, 'tenants/invite.html', {'invitations': invitations})
