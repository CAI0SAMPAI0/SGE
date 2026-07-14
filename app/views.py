import json
import logging
import os
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ai.models import AIResult
from . import metrics
from .models import SiteSettings, UserProfile


logger = logging.getLogger(__name__)


@login_required(login_url='login')
def home(request):
    product_metrics = metrics.get_product_metrics(tenant=request.tenant)
    sales_metrics = metrics.get_sales_metrics(tenant=request.tenant)
    graphic_product_category_metric = metrics.get_graphic_product_category_metric(tenant=request.tenant)
    graphic_product_brand_metric = metrics.get_graphic_product_brand_metric(tenant=request.tenant)
    daily_sales_data = metrics.get_daily_sales_data(tenant=request.tenant)
    daily_sales_quantity_data = metrics.get_daily_sales_quantity_data(tenant=request.tenant)
    ai_result = AIResult.objects.filter(tenant=request.tenant).first()
    ai_result = ai_result.result if ai_result else ''

    context = {
        'product_metrics': product_metrics,
        'sales_metrics': sales_metrics,
        'product_count_by_category': json.dumps(graphic_product_category_metric),
        'product_count_by_brand': json.dumps(graphic_product_brand_metric),
        'daily_sales_data': json.dumps(daily_sales_data),
        'daily_sales_quantity_data': json.dumps(daily_sales_quantity_data),
        'ai_result': ai_result,
    }

    return render(request, 'home.html', context)


@login_required(login_url='login')
def data_import(request):
    preview = None
    columns = []
    field_mapping = {}

    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            messages.error(request, 'Selecione um arquivo.')
            return redirect('data_import')

        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ('.csv', '.xlsx', '.xls'):
            messages.error(request, 'Formato aceito: CSV ou Excel (.xlsx, .xls).')
            return redirect('data_import')

        # Salva arquivo temporario
        tmp_dir = settings.MEDIA_ROOT / 'imports'
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = tmp_dir / f'{uuid.uuid4().hex}{ext}'
        with open(tmp_path, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)

        # Le o arquivo
        import pandas as pd
        try:
            if ext == '.csv':
                df = pd.read_csv(tmp_path, encoding='utf-8')
            else:
                df = pd.read_excel(tmp_path)
        except Exception as e:
            os.remove(tmp_path)
            messages.error(request, f'Erro ao ler arquivo: {e}')
            return redirect('data_import')

        columns = list(df.columns)
        preview = df.head(10).to_dict('records')

        # Detecta mapeamento com IA
        if columns:
            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)
            prompt = f"""Mapeie as colunas abaixo para os campos do sistema de estoque.
Colunas do arquivo: {columns}

Campos disponiveis: title (nome obrigatorio), category_name, brand_name, cost_price, selling_price, quantity, serie_number.

Responda APENAS JSON sem comentarios, ex: {{"title": "Nome do Produto", "quantity": "Qtd"}}
Use null para colunas sem correspondencia. Se title nao for encontrado, use a primeira coluna."""
            try:
                resp = client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=[{'role': 'user', 'content': prompt}],
                    temperature=0.1,
                )
                field_mapping = json.loads(resp.choices[0].message.content.strip())
                if not isinstance(field_mapping, dict):
                    field_mapping = {}
            except Exception:
                field_mapping = {}

        # Salva na sessao para confirmacao
        request.session['import_file'] = str(tmp_path)
        request.session['import_columns'] = columns
        request.session['import_mapping'] = field_mapping

    return render(request, 'data_import.html', {
        'columns': columns,
        'preview': preview,
        'field_mapping': field_mapping,
    })


@require_POST
@login_required(login_url='login')
def data_import_confirm(request):
    file_path = request.session.get('import_file')
    if not file_path or not os.path.exists(file_path):
        messages.error(request, 'Arquivo nao encontrado. Faca o upload novamente.')
        return redirect('data_import')

    field_mapping = request.POST.get('mapping', '{}')
    try:
        field_mapping = json.loads(field_mapping)
    except json.JSONDecodeError:
        field_mapping = request.session.get('import_mapping', {})

    from .tasks import process_import
    try:
        task = process_import.delay(
            file_path=file_path,
            tenant_id=request.tenant.id if request.tenant else None,
            user_id=request.user.id,
            field_mapping=field_mapping,
        )
        messages.success(request, f'Importacao iniciada! Task ID: {task.id}')
    except Exception:
        results = process_import(
            file_path=file_path,
            tenant_id=request.tenant.id if request.tenant else None,
            user_id=request.user.id,
            field_mapping=field_mapping,
        )
        messages.success(
            request,
            f'Importacao concluida! {results.get("created", 0)} produtos criados.'
        )
        if results.get('errors'):
            for err in results['errors'][:5]:
                messages.warning(request, err)

    del request.session['import_file']
    del request.session['import_columns']
    del request.session['import_mapping']

    return redirect('product_list')


@login_required(login_url='login')
def profile_edit(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        action = request.POST.get('action', 'profile')
        if action == 'profile':
            request.user.first_name = request.POST.get('first_name', '')
            request.user.last_name = request.POST.get('last_name', '')
            request.user.email = request.POST.get('email', '')
            request.user.username = request.POST.get('username', request.user.username)
            request.user.save()
            profile.phone = request.POST.get('phone', '')
            profile.save()
            messages.success(request, 'Perfil atualizado com sucesso.')
        elif action == 'password':
            form = PasswordChangeForm(request.user, request.POST)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Senha alterada com sucesso.')
            else:
                for field, errors in form.errors.items():
                    for e in errors:
                        messages.error(request, f'{field}: {e}')
        return redirect('profile_edit')

    form = PasswordChangeForm(request.user)
    return render(request, 'profile.html', {'profile': profile, 'password_form': form})


@login_required(login_url='login')
def settings_view(request):
    settings_obj, _ = SiteSettings.objects.get_or_create(pk=1)
    groups = Group.objects.all().order_by('name')
    users = User.objects.all().order_by('username')
    all_permissions = Permission.objects.select_related('content_type').order_by(
        'content_type__app_label', 'content_type__model', 'codename'
    )
    perm_groups = {}
    for p in all_permissions:
        key = f"{p.content_type.app_label} | {p.content_type.model}"
        perm_groups.setdefault(key, []).append(p)

    context = {
        'settings': settings_obj,
        'groups': groups,
        'users': users,
        'perm_groups': perm_groups,
    }
    return render(request, 'settings/settings.html', context)


@require_POST
@login_required(login_url='login')
def save_theme(request):
    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalido.'}, status=400)
    theme = payload.get('theme', 'dark')
    if theme not in ('dark', 'light'):
        return JsonResponse({'error': 'Tema invalido.'}, status=400)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.theme = theme
    profile.save()
    return JsonResponse({'theme': theme})


@require_POST
@login_required(login_url='login')
def group_create(request):
    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Nome do grupo e obrigatorio.')
        return redirect('settings')
    group, created = Group.objects.get_or_create(name=name)
    if not created:
        messages.warning(request, f'Grupo "{name}" ja existe.')
    else:
        messages.success(request, f'Grupo "{name}" criado.')
    perm_ids = request.POST.getlist('permissions')
    group.permissions.set(Permission.objects.filter(id__in=perm_ids))
    return redirect('settings')


@require_POST
@login_required(login_url='login')
def group_edit(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    name = request.POST.get('name', '').strip()
    if name:
        group.name = name
        group.save()
    perm_ids = request.POST.getlist('permissions')
    group.permissions.set(Permission.objects.filter(id__in=perm_ids))
    messages.success(request, f'Grupo "{group.name}" atualizado.')
    return redirect('settings')


@require_POST
@login_required(login_url='login')
def group_delete(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    name = group.name
    group.delete()
    messages.success(request, f'Grupo "{name}" excluido.')
    return redirect('settings')


@require_POST
@login_required(login_url='login')
def user_edit(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    target.first_name = request.POST.get('first_name', target.first_name)
    target.last_name = request.POST.get('last_name', target.last_name)
    target.email = request.POST.get('email', target.email)
    target.is_active = request.POST.get('is_active') == 'on'
    is_staff = request.POST.get('is_staff') == 'on'
    if request.user.is_superuser:
        target.is_staff = is_staff
    target.save()
    group_ids = request.POST.getlist('groups')
    target.groups.set(Group.objects.filter(id__in=group_ids))
    messages.success(request, f'Usuario "{target.username}" atualizado.')
    return redirect('settings')
