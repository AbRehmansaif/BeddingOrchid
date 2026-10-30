from django.core.management.base import BaseCommand
from decimal import Decimal
from apps.catalog.models import Product, Size, Color, ProductVariant

class Command(BaseCommand):
    help = 'Generate standard King, Queen, Single, Super King variants for all products'

    def handle(self, *args, **options):
        sizes = list(Size.objects.filter(name__in=['King', 'Queen', 'Single', 'Super King']))
        colors = list(Color.objects.all()[:3])
        if not sizes:
            self.stdout.write(self.style.ERROR('No sizes found.'))
            return

        total_created = 0
        for p in Product.objects.all():
            for s in sizes:
                for c in colors:
                    sku = f"BTX-P{p.id}-S{s.id}-C{c.id}"
                    p_diff = Decimal('0.00')
                    if s.name == 'Single':
                        p_diff = -Decimal('500.00')
                    elif s.name == 'Super King':
                        p_diff = Decimal('500.00')
                    elif s.name == 'Queen':
                        p_diff = -Decimal('200.00')
                    
                    v_price = max(Decimal('500.00'), p.base_price + p_diff)
                    _, created = ProductVariant.objects.get_or_create(
                        product=p, size=s, color=c,
                        defaults={
                            'sku': sku,
                            'stock_quantity': 35,
                            'price': v_price,
                            'compare_at_price': p.compare_at_price,
                        }
                    )
                    if created:
                        total_created += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully generated {total_created} size variants across all products.'))
