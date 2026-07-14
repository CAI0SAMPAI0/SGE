import json
import urllib.request
import urllib.parse
from decimal import Decimal, InvalidOperation

from django.db import transaction
from products.models import Product
from brands.models import Brand
from categories.models import Category
from suppliers.models import Supplier
from outflows.models import Outflow
from inflows.models import Inflow


def get_tool_schemas():
    return [
        {
            'type': 'function',
            'function': {
                'name': 'list_products',
                'description': 'Lista produtos do estoque. Use para responder perguntas sobre o que há em estoque.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'search': {
                            'type': 'string',
                            'description': 'Termo de busca opcional para filtrar por nome do produto.',
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Numero maximo de resultados (padrao 20).',
                        },
                    },
                },
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'add_product',
                'description': 'Adiciona um novo produto ao estoque. Requer titulo, categoria, marca, preco de custo, preco de venda e quantidade.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string', 'description': 'Nome do produto.'},
                        'category_name': {'type': 'string', 'description': 'Nome da categoria.'},
                        'brand_name': {'type': 'string', 'description': 'Nome da marca.'},
                        'cost_price': {'type': 'number', 'description': 'Preco de custo.'},
                        'selling_price': {'type': 'number', 'description': 'Preco de venda.'},
                        'quantity': {'type': 'integer', 'description': 'Quantidade inicial em estoque.'},
                    },
                    'required': ['title', 'category_name', 'brand_name', 'cost_price', 'selling_price', 'quantity'],
                },
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'update_stock',
                'description': 'Atualiza a quantidade em estoque de um produto (adiciona ou remove). Use para entradas ou saidas de estoque.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'product_id': {'type': 'integer', 'description': 'ID do produto.'},
                        'delta': {'type': 'integer', 'description': 'Quantidade a adicionar (positivo) ou remover (negativo).'},
                    },
                    'required': ['product_id', 'delta'],
                },
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'get_stock_summary',
                'description': 'Retorna um resumo do estoque: total de produtos, valor total de custo, valor total de venda, lucro potencial e produtos com baixo estoque.',
                'parameters': {'type': 'object', 'properties': {}},
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'list_outflows',
                'description': 'Lista as saidas recentes (vendas). Use para responder sobre vendas.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'limit': {'type': 'integer', 'description': 'Numero maximo de resultados (padrao 20).'},
                    },
                },
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'search_web_price',
                'description': 'Busca na web por precos de mercado de um produto para ajudar a precificar. Retorna resultados de busca relevantes.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string', 'description': 'Termo de busca (nome do produto + "preco").'},
                    },
                    'required': ['query'],
                },
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'list_brands',
                'description': 'Lista todas as marcas cadastradas.',
                'parameters': {'type': 'object', 'properties': {}},
            },
        },
        {
            'type': 'function',
            'function': {
                'name': 'list_categories',
                'description': 'Lista todas as categorias cadastradas.',
                'parameters': {'type': 'object', 'properties': {}},
            },
        },
    ]


def execute_tool(name, args, user, tenant=None):
    dispatch = {
        'list_products': _list_products,
        'add_product': _add_product,
        'update_stock': _update_stock,
        'get_stock_summary': _get_stock_summary,
        'list_outflows': _list_outflows,
        'search_web_price': _search_web_price,
        'list_brands': _list_brands,
        'list_categories': _list_categories,
    }
    fn = dispatch.get(name)
    if not fn:
        return {'error': f'Ferramenta "{name}" nao encontrada.'}
    try:
        return fn(args, user, tenant)
    except Exception as e:
        return {'error': str(e)}


def _list_products(args, user, tenant=None):
    qs = Product.objects.select_related('brand', 'category')
    if tenant:
        qs = qs.filter(tenant=tenant)
    search = args.get('search', '')
    if search:
        qs = qs.filter(title__icontains=search)
    limit = min(args.get('limit', 20), 50)
    products = qs[:limit]
    return {
        'count': len(products),
        'products': [
            {
                'id': p.id,
                'titulo': p.title,
                'marca': p.brand.name,
                'categoria': p.category.name,
                'estoque': p.quantity,
                'preco_custo': float(p.cost_price),
                'preco_venda': float(p.selling_price),
            }
            for p in products
        ],
    }


def _add_product(args, user, tenant=None):
    category, _ = Category.objects.get_or_create(name__iexact=args['category_name'], defaults={'name': args['category_name']})
    brand, _ = Brand.objects.get_or_create(name__iexact=args['brand_name'], defaults={'name': args['brand_name']})
    product = Product.objects.create(
        title=args['title'],
        category=category,
        brand=brand,
        cost_price=Decimal(str(args['cost_price'])),
        selling_price=Decimal(str(args['selling_price'])),
        quantity=args['quantity'],
    )
    if tenant:
        product.tenant = tenant
        product.save(update_fields=['tenant'])
    return {'success': True, 'product_id': product.id, 'message': f'Produto "{product.title}" criado com estoque de {product.quantity} unidades.'}


def _update_stock(args, user, tenant=None):
    pid = args['product_id']
    delta = args['delta']
    qs = Product.objects.select_for_update()
    if tenant:
        qs = qs.filter(tenant=tenant)
    try:
        product = qs.get(pk=pid)
    except Product.DoesNotExist:
        return {'error': f'Produto ID {pid} nao encontrado.'}
    product.quantity += delta
    if product.quantity < 0:
        product.quantity = 0
    product.save(update_fields=['quantity', 'updated_at'])
    return {
        'success': True,
        'product_id': product.id,
        'new_quantity': product.quantity,
        'message': f'Estoque de "{product.title}" ajustado para {product.quantity} unidades.',
    }


def _get_stock_summary(args, user, tenant=None):
    from django.db.models import Sum
    qs = Product.objects.all()
    if tenant:
        qs = qs.filter(tenant=tenant)
    total_qty = qs.aggregate(s=Sum('quantity'))['s'] or 0
    total_cost = qs.aggregate(s=Sum('cost_price'))['s'] or 0
    total_sale = qs.aggregate(s=Sum('selling_price'))['s'] or 0
    low_stock = [
        {'id': p.id, 'titulo': p.title, 'estoque': p.quantity}
        for p in qs.filter(quantity__lte=5).order_by('quantity')[:10]
    ]
    return {
        'total_produtos': qs.count(),
        'total_unidades': total_qty,
        'valor_custo': float(total_cost),
        'valor_venda': float(total_sale),
        'lucro_potencial': float(total_sale - total_cost),
        'estoque_baixo': low_stock,
    }


def _list_outflows(args, user, tenant=None):
    limit = min(args.get('limit', 20), 50)
    qs = Outflow.objects.select_related('product').order_by('-created_at')
    if tenant:
        qs = qs.filter(tenant=tenant)
    outflows = qs[:limit]
    return {
        'count': len(outflows),
        'outflows': [
            {
                'produto': o.product.title,
                'quantidade': o.quantity,
                'data': o.created_at.strftime('%Y-%m-%d %H:%M'),
                'descricao': o.description or '',
            }
            for o in outflows
        ],
    }


def _search_web_price(args, user, tenant=None):
    query = args.get('query', '')
    if not query:
        return {'error': 'Termo de busca vazio.'}
    url = 'https://api.duckduckgo.com/?' + urllib.parse.urlencode({
        'q': query,
        'format': 'json',
        'no_html': '1',
        'skip_disambig': '1',
    })
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SGE-Agent/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        results = []
        if data.get('AbstractText'):
            results.append({'title': data.get('Heading', ''), 'text': data['AbstractText'], 'source': data.get('AbstractURL', '')})
        for r in data.get('RelatedTopics', [])[:5]:
            if isinstance(r, dict) and r.get('Text'):
                results.append({'title': r.get('Text', '')[:100], 'text': r.get('Text', ''), 'source': r.get('FirstURL', '')})
        if not results:
            return {'message': 'Nenhum resultado encontrado. Recomendo pesquisar manualmente no Google ou Mercado Livre por "' + query + '".'}
        return {'query': query, 'results': results}
    except Exception as e:
        return {'error': f'Falha na busca: {e}. Recomendo pesquisar manualmente por "{query}".'}


def _list_brands(args, user, tenant=None):
    qs = Brand.objects.all()
    if tenant:
        qs = qs.filter(tenant=tenant)
    brands = qs[:50]
    return {'brands': [b.name for b in brands]}


def _list_categories(args, user, tenant=None):
    qs = Category.objects.all()
    if tenant:
        qs = qs.filter(tenant=tenant)
    cats = qs[:50]
    return {'categories': [c.name for c in cats]}
