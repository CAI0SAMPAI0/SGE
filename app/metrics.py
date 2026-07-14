from django.db.models import Sum, F
from django.utils.formats import number_format
from django.utils import timezone
from brands.models import Brand
from categories.models import Category
from products.models import Product
from outflows.models import Outflow


def get_product_metrics(tenant=None):
    products = Product.objects.all()
    if tenant:
        products = products.filter(tenant=tenant)
    total_cost_price = sum(product.cost_price * product.quantity for product in products)
    total_selling_price = sum(product.selling_price * product.quantity for product in products)
    total_quantity = sum(product.quantity for product in products)
    total_profit = total_selling_price - total_cost_price

    return dict(
        total_cost_price=number_format(total_cost_price, decimal_pos=2, force_grouping=True),
        total_selling_price=number_format(total_selling_price, decimal_pos=2, force_grouping=True),
        total_quantity=total_quantity,
        total_profit=number_format(total_profit, decimal_pos=2, force_grouping=True),
    )


def get_sales_metrics(tenant=None):
    qs = Outflow.objects.all()
    if tenant:
        qs = qs.filter(tenant=tenant)
    total_sales = qs.count()
    total_products_sold = qs.aggregate(total_products_sold=Sum('quantity'))['total_products_sold'] or 0
    outflows = qs.select_related('product')
    total_sales_value = sum(o.quantity * o.product.selling_price for o in outflows)
    total_sales_cost = sum(o.quantity * o.product.cost_price for o in outflows)
    total_sales_profit = total_sales_value - total_sales_cost

    return dict(
        total_sales=total_sales,
        total_products_sold=total_products_sold,
        total_sales_value=number_format(total_sales_value, decimal_pos=2, force_grouping=True),
        total_sales_profit=number_format(total_sales_profit, decimal_pos=2, force_grouping=True),
    )


def get_daily_sales_data(tenant=None):
    today = timezone.now().date()
    dates = [str(today - timezone.timedelta(days=i)) for i in range(6, -1, -1)]
    values = list()

    qs = Outflow.objects.all()
    if tenant:
        qs = qs.filter(tenant=tenant)

    for date in dates:
        sales_total = qs.filter(
            created_at__date=date
        ).aggregate(
            total_sales=Sum(F('product__selling_price') * F('quantity'))
        )['total_sales'] or 0
        values.append(float(sales_total))

    return dict(
        dates=dates,
        values=values,
    )


def get_daily_sales_quantity_data(tenant=None):
    today = timezone.now().date()
    dates = [str(today - timezone.timedelta(days=i)) for i in range(6, -1, -1)]
    quantities = list()

    qs = Outflow.objects.all()
    if tenant:
        qs = qs.filter(tenant=tenant)

    for date in dates:
        sales_quantity = qs.filter(created_at__date=date).count()
        quantities.append(sales_quantity)

    return dict(
        dates=dates,
        values=quantities,
    )


def get_graphic_product_category_metric(tenant=None):
    categories = Category.objects.all()
    if tenant:
        categories = categories.filter(tenant=tenant)
    return {c.name: Product.objects.filter(category=c).count() for c in categories}


def get_graphic_product_brand_metric(tenant=None):
    brands = Brand.objects.all()
    if tenant:
        brands = brands.filter(tenant=tenant)
    return {b.name: Product.objects.filter(brand=b).count() for b in brands}
