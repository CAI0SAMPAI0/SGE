import json
from django.conf import settings
from groq import Groq
from ai import prompts, models
from products.models import Product
from outflows.models import Outflow


class SGEAgent:

    def __init__(self):
        self.__client = Groq(
            api_key=settings.GROQ_API_KEY,
        )

    def __get_data(self):
        # Limit to avoid exceeding free-tier token limits
        products = (
            Product.objects
            .select_related('brand', 'category')
            .order_by('quantity')[:20]  # 20 products with lowest stock
        )
        outflows = (
            Outflow.objects
            .select_related('product')
            .order_by('-created_at')[:30]  # 30 most recent outflows
        )

        products_summary = [
            {
                'produto': p.title,
                'marca': p.brand.name,
                'estoque': p.quantity,
                'preco_venda': float(p.selling_price),
            }
            for p in products
        ]

        outflows_summary = [
            {
                'produto': o.product.title,
                'quantidade': o.quantity,
                'data': o.created_at.strftime('%Y-%m-%d'),
            }
            for o in outflows
        ]

        return json.dumps({
            'produtos': products_summary,
            'saidas': outflows_summary,
        }, ensure_ascii=False)

    def invoke(self):
        response = self.__client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {
                    'role': 'system',
                    'content': prompts.SYSTEM_PROMPT,
                },
                {
                    'role': 'user',
                    'content': prompts.USER_PROMPT.replace('{{data}}', self.__get_data()),
                },
            ],
            temperature=0.7
        )
        result = response.choices[0].message.content
        models.AIResult.objects.create(result=result)
