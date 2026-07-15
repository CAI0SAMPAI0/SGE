import json
import os
import csv
from decimal import Decimal

from celery import shared_task


def _ai_infer_fields(rows_with_titles):
    """Chama Groq pra inferir marca, categoria e descrição dos produtos."""
    from django.conf import settings
    from groq import Groq

    titles = [r['title'] for r in rows_with_titles]
    prompt = f"""Você é um especialista em categorização de produtos.
Para cada produto abaixo, infira a CATEGORIA, MARCA e DESCRIÇÃO mais prováveis.

Regras:
- Categoria: use categorias genéricas como "Eletrônicos", "Alimentos", "Roupas", "Ferramentas", "Limpeza", "Papelaria", "Automotivo", "Móveis", "Esportes", "Beleza", "Brinquedos", "Livros", "Bebidas", "Casa", "Jardim", "Pet Shop", etc.
- Marca: extraia do nome do produto se possível. Se não der pra identificar, use "Genérica".
- Descrição: gere 1 frase curta descrevendo o produto.

Responda APENAS JSON, sem comentários, formato:
{{"inferencias": [{{"title": "Nome do Produto", "category": "Categoria", "brand": "Marca", "description": "Descrição"}}]}}

Produtos:
{chr(10).join(f'{i+1}. {t}' for i, t in enumerate(titles))}"""

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.2,
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith('```'):
            content = content.split('\n', 1)[-1].rsplit('\n', 1)[0]
            if content.endswith('```'):
                content = content[:-3]
        result = json.loads(content)
        return {item['title']: item for item in result.get('inferencias', [])}
    except Exception:
        return {}


@shared_task(bind=True, max_retries=3)
def process_import(self, file_path, tenant_id, user_id, field_mapping):
    from django.contrib.auth.models import User
    from tenants.models import Tenant
    from products.models import Product
    from brands.models import Brand
    from categories.models import Category

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

            # Primeira passada: extrai dados e identifica quais precisam de inferência
            parsed = []
            need_inference = []
            for i, row in enumerate(rows, 1):
                try:
                    data = {k: row.get(v, '') for k, v in field_mapping.items()}
                    if not data.get('title'):
                        results['errors'].append(f'Linha {i}: título vazio')
                        continue

                    title = data.get('title', '').strip()
                    category_name = (data.pop('category_name', '') or '').strip()
                    brand_name = (data.pop('brand_name', '') or '').strip()
                    description = (data.pop('description', '') or '').strip()

                    parsed.append({
                        'title': title,
                        'category_name': category_name,
                        'brand_name': brand_name,
                        'description': description,
                        'cost_price': data.get('cost_price', 0),
                        'selling_price': data.get('selling_price', 0),
                        'quantity': data.get('quantity', 0),
                        'serie_number': data.get('serie_number', ''),
                        'row': i,
                    })

                    if not category_name or not brand_name or not description:
                        need_inference.append(parsed[-1])

                except Exception as e:
                    results['errors'].append(f'Linha {i}: {str(e)}')

            # Inferência via IA para campos faltantes
            inferences = {}
            if need_inference:
                inferences = _ai_infer_fields(need_inference)

            # Segunda passada: cria os produtos
            for item in parsed:
                try:
                    inf = inferences.get(item['title'], {})

                    category_name = item['category_name'] or inf.get('category', '') or 'Geral'
                    brand_name = item['brand_name'] or inf.get('brand', '') or 'Genérica'
                    description = item['description'] or inf.get('description', '')

                    category, _ = Category.objects.get_or_create(
                        name__iexact=category_name,
                        defaults={'name': category_name, 'tenant': tenant},
                    )
                    brand, _ = Brand.objects.get_or_create(
                        name__iexact=brand_name,
                        defaults={'name': brand_name, 'tenant': tenant},
                    )

                    Product.objects.create(
                        title=item['title'],
                        category=category,
                        brand=brand,
                        description=description or None,
                        cost_price=Decimal(str(item['cost_price'] or 0)),
                        selling_price=Decimal(str(item['selling_price'] or 0)),
                        quantity=int(item['quantity'] or 0),
                        serie_number=item['serie_number'] or '',
                        tenant=tenant,
                    )
                    results['created'] += 1
                except Exception as e:
                    results['errors'].append(f'Linha {item["row"]}: {str(e)}')

    except Exception as e:
        results['errors'].append(f'Erro ao ler arquivo: {str(e)}')

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
