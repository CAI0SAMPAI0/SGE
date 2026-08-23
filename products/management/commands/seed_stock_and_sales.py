import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from products.models import Product
from brands.models import Brand
from categories.models import Category
from suppliers.models import Supplier
from inflows.models import Inflow
from outflows.models import Outflow
from tenants.models import Tenant


class Command(BaseCommand):
    help = 'Adiciona estoque (entradas) e registra saídas (vendas) aleatórias para os produtos no banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Limpa entradas e saídas existentes antes de gerar novas.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Iniciando povoamento de estoque e vendas...'))

        tenant = Tenant.objects.first()
        if not tenant:
            tenant = Tenant.objects.create(name='Empresa Principal')
            self.stdout.write(self.style.SUCCESS(f'Tenant criado: {tenant.name}'))

        # Vincula dados sem tenant ao tenant principal
        Brand.objects.filter(tenant__isnull=True).update(tenant=tenant)
        Category.objects.filter(tenant__isnull=True).update(tenant=tenant)
        Product.objects.filter(tenant__isnull=True).update(tenant=tenant)
        Supplier.objects.filter(tenant__isnull=True).update(tenant=tenant)

        # Cria fornecedores caso nao existam
        supplier_names = [
            'Distribuidora Tech Brasil',
            'Logitech Brasil Oficial',
            'Eletrônicos & Cia Importadora',
            'MegaDistribuidor Hardware',
            'Global Express Suprimentos',
        ]
        suppliers = []
        for name in supplier_names:
            sup, _ = Supplier.objects.get_or_create(
                name=name,
                defaults={'description': f'Fornecedor parceiro {name}', 'tenant': tenant},
            )
            if not sup.tenant:
                sup.tenant = tenant
                sup.save()
            suppliers.append(sup)

        if options['clear']:
            self.stdout.write(self.style.WARNING('Limpando Inflows e Outflows anteriores...'))
            Outflow.objects.filter(tenant=tenant).delete()
            Inflow.objects.filter(tenant=tenant).delete()
            Product.objects.filter(tenant=tenant).update(quantity=0)

        products = list(Product.objects.filter(tenant=tenant))
        if not products:
            self.stdout.write(self.style.ERROR('Nenhum produto encontrado no banco de dados.'))
            return

        self.stdout.write(f'Encontrados {len(products)} produtos para o tenant "{tenant.name}".')

        now = timezone.now()
        sale_descriptions = [
            'Venda Balcão',
            'Pedido E-commerce',
            'Venda WhatsApp',
            'Pedido Mercado Livre',
            'Venda Presencial Loja',
            'Pedido B2B Corporativo',
            'Venda Direta Representante',
            'Pedido Shopee',
        ]

        inflow_count = 0
        outflow_count = 0
        total_units_in = 0
        total_units_out = 0

        with transaction.atomic():
            for product in products:
                # 1. Cria uma ou duas entradas para garantir estoque inicial robusto (ex: 40 a 120 unidades)
                supplier = random.choice(suppliers)
                initial_inflow_qty = random.randint(50, 150)
                
                # Inflow criado
                inflow = Inflow.objects.create(
                    supplier=supplier,
                    product=product,
                    quantity=initial_inflow_qty,
                    description=f'Entrada Lote Inicial NF #{random.randint(1000, 9999)}',
                    tenant=tenant,
                )
                inflow_date = now - timedelta(days=random.randint(15, 45), hours=random.randint(1, 23))
                Inflow.objects.filter(id=inflow.id).update(created_at=inflow_date, updated_at=inflow_date)
                
                inflow_count += 1
                total_units_in += initial_inflow_qty

                # 2. Gera vendas (saídas) aleatórias para este produto
                # Quantidade de transações de venda por produto (entre 4 e 15 vendas)
                num_sales = random.randint(4, 15)
                for _ in range(num_sales):
                    # Recarrega o produto para pegar quantidade atual
                    product.refresh_from_db()
                    if product.quantity <= 5:
                        break  # Mantem margem de seguranca de estoque

                    sale_qty = random.randint(1, min(4, product.quantity - 2))
                    if sale_qty <= 0:
                        continue

                    sale_desc = f"{random.choice(sale_descriptions)} #{random.randint(10000, 99999)}"
                    
                    # Criar Outflow
                    outflow = Outflow.objects.create(
                        product=product,
                        quantity=sale_qty,
                        description=sale_desc,
                        tenant=tenant,
                    )

                    # Distribuicao de datas: 60% nos ultimos 7 dias (para graficos diarios do dashboard) e 40% nos ultimos 30 dias
                    if random.random() < 0.60:
                        days_ago = random.randint(0, 6)
                    else:
                        days_ago = random.randint(7, 30)

                    sale_date = now - timedelta(
                        days=days_ago,
                        hours=random.randint(0, 23),
                        minutes=random.randint(0, 59),
                    )
                    Outflow.objects.filter(id=outflow.id).update(created_at=sale_date, updated_at=sale_date)

                    outflow_count += 1
                    total_units_out += sale_qty

        self.stdout.write(self.style.SUCCESS(
            f'\n[SUCESSO] Processo concluido com sucesso!'
            f'\n- Produtos processados: {len(products)}'
            f'\n- Entradas registradas: {inflow_count} ({total_units_in} unidades totais)'
            f'\n- Vendas (saidas) geradas: {outflow_count} ({total_units_out} unidades vendidas)'
            f'\n- Saldo de estoque atualizado e consistente.'
        ))
