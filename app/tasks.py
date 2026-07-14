from celery import shared_task


@shared_task(bind=True, max_retries=3)
def process_import(self, file_path, tenant_id, user_id, field_mapping):
    from io import StringIO
    import csv
    from django.contrib.auth.models import User
    from tenants.models import Tenant
    from products.models import Product
    from brands.models import Brand
    from categories.models import Category
    from decimal import Decimal

    tenant = None
    if tenant_id:
        from tenants.models import Tenant
        tenant = Tenant.objects.get(pk=tenant_id)
    user = User.objects.get(pk=user_id)
    results = {'created': 0, 'errors': [], 'total': 0}

    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            results['total'] = len(rows)

            for i, row in enumerate(rows, 1):
                try:
                    data = {k: row.get(v, '') for k, v in field_mapping.items()}
                    if not data.get('title'):
                        results['errors'].append(f'Linha {i}: titulo vazio')
                        continue

                    category_name = data.pop('category_name', '') or 'Geral'
                    brand_name = data.pop('brand_name', '') or 'Generica'

                    category, _ = Category.objects.get_or_create(
                        name__iexact=category_name,
                        defaults={'name': category_name, 'tenant': tenant},
                    )
                    brand, _ = Brand.objects.get_or_create(
                        name__iexact=brand_name,
                        defaults={'name': brand_name, 'tenant': tenant},
                    )

                    Product.objects.create(
                        title=data.get('title', ''),
                        category=category,
                        brand=brand,
                        cost_price=Decimal(str(data.get('cost_price', 0) or 0)),
                        selling_price=Decimal(str(data.get('selling_price', 0) or 0)),
                        quantity=int(data.get('quantity', 0) or 0),
                        tenant=tenant,
                    )
                    results['created'] += 1
                except Exception as e:
                    results['errors'].append(f'Linha {i}: {str(e)}')

    except Exception as e:
        results['errors'].append(f'Erro ao ler arquivo: {str(e)}')

    import os
    try:
        os.remove(file_path)
    except OSError:
        pass

    return results


@shared_task(bind=True, max_retries=3)
def ai_analyze_inventory(self, tenant_id):
    from ai.agent import SGEAgent
    agent = SGEAgent(tenant_id)
    agent.invoke()
    return {'status': 'ok', 'tenant_id': tenant_id}
