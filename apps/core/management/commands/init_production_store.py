"""
Django management command to bootstrap a production BeddingOrchid database with:
- Core SiteSettings (store contact, currency, delivery thresholds)
- Master Bedding Category Taxonomy (MPTT)
- Standard Bedding Sizes & Dimensions
- Standard Luxury Textile Fabric Colors
- Mandatory Legal & CMS Policy Pages (About Us, Returns, Shipping, Privacy, Terms)
- Optional Administrator Superuser

ZERO dummy products, ZERO dummy orders, ZERO dummy reviews are created.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.core.models import SiteSettings
from apps.pages.models import Page
from apps.catalog.models import Category, Size, Color

User = get_user_model()

class Command(BaseCommand):
    help = 'Initializes clean production baseline for BeddingOrchid (No dummy products/orders).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-email',
            type=str,
            default='admin@beddingorchid.com',
            help='Superuser email address (default: admin@beddingorchid.com)'
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            default='BeddingOrchid2024!',
            help='Superuser password (default: BeddingOrchid2024!)'
        )
        parser.add_argument(
            '--skip-admin',
            action='store_true',
            help='Skip superuser creation'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== Bootstrapping BeddingOrchid Production Database ==="))

        # 1. Superuser
        if not options['skip_admin']:
            admin_email = options['admin_email']
            admin_password = options['admin_password']
            if not User.objects.filter(username='admin').exists() and not User.objects.filter(email=admin_email).exists():
                User.objects.create_superuser(
                    username='admin',
                    email=admin_email,
                    password=admin_password,
                    full_name='BeddingOrchid Administrator',
                    phone='923000000000'
                )
                self.stdout.write(self.style.SUCCESS(f"[OK] Created superuser: {admin_email}"))
            else:
                self.stdout.write(self.style.WARNING("[!] Superuser already exists. Skipping creation."))

        # 2. SiteSettings Singleton
        settings_obj = SiteSettings.get_settings()
        settings_obj.store_name = 'BeddingOrchid'
        settings_obj.tagline = 'Luxury Bedding & Home Textiles — Crafted for Serene Sleep'
        settings_obj.phone = '+92 300 1234567'
        settings_obj.whatsapp_number = '923001234567'
        settings_obj.email = 'orders@beddingorchid.com'
        settings_obj.address = 'Plot 45-B, Textile Avenue, Industrial Zone, Karachi, Pakistan'
        settings_obj.currency = 'PKR'
        settings_obj.currency_symbol = 'Rs.'
        settings_obj.default_shipping_fee = Decimal('250.00')
        settings_obj.free_shipping_threshold = Decimal('4000.00')
        settings_obj.default_cod_fee = Decimal('0.00')
        settings_obj.max_cod_amount = Decimal('60000.00')
        settings_obj.announcement_bar_text = '✨ Free Nationwide Delivery on orders above Rs. 4,000 | Cash on Delivery Available'
        settings_obj.announcement_bar_link = '/collections/bed-sheets/'
        settings_obj.footer_about_text = (
            "BeddingOrchid is Pakistan's premier luxury bedding brand. "
            "We handcraft hotel-grade bed sheets, plush quilts, and luxury duvet covers using 100% combed cotton."
        )
        settings_obj.save()
        self.stdout.write(self.style.SUCCESS("[OK] Configured SiteSettings"))

        # 3. Categories (MPTT Hierarchy)
        categories_structure = [
            {
                'name': 'Bed Sheets',
                'slug': 'bed-sheets',
                'children': [
                    {'name': 'Luxury Sateen Bed Sheets', 'slug': 'luxury-sateen-bed-sheets'},
                    {'name': 'Cotton Percale Sets', 'slug': 'cotton-percale-sets'},
                    {'name': 'Fitted Bed Sheets', 'slug': 'fitted-bed-sheets'},
                    {'name': 'Printed & Floral Sets', 'slug': 'printed-floral-sets'},
                    {'name': 'Bridal & Velvet Sets', 'slug': 'bridal-velvet-sets'},
                ]
            },
            {
                'name': 'Duvet & Quilt Covers',
                'slug': 'duvet-quilt-covers',
                'children': [
                    {'name': 'Solid Duvet Sets', 'slug': 'solid-duvet-sets'},
                    {'name': 'Embroidered Quilt Covers', 'slug': 'embroidered-quilt-covers'},
                    {'name': 'Luxury Velvet Covers', 'slug': 'luxury-velvet-covers'},
                ]
            },
            {
                'name': 'Comforters & Quilts',
                'slug': 'comforters-quilts',
                'children': [
                    {'name': 'All-Season Comforters', 'slug': 'all-season-comforters'},
                    {'name': 'Heavy Winter Quilts', 'slug': 'heavy-winter-quilts'},
                    {'name': 'Fluffy Throw Blankets', 'slug': 'fluffy-throw-blankets'},
                ]
            },
            {
                'name': 'Pillows & Protectors',
                'slug': 'pillows-protectors',
                'children': [
                    {'name': 'Hotel Luxury Pillows', 'slug': 'hotel-luxury-pillows'},
                    {'name': 'Waterproof Mattress Protectors', 'slug': 'waterproof-mattress-protectors'},
                ]
            },
            {
                'name': 'Living & Cushions',
                'slug': 'living-cushions',
                'children': [
                    {'name': 'Decorative Cushion Covers', 'slug': 'decorative-cushion-covers'},
                    {'name': 'Quilted Sofa Covers', 'slug': 'quilted-sofa-covers'},
                ]
            },
        ]

        cat_count = 0
        for p_data in categories_structure:
            parent_cat, _ = Category.objects.update_or_create(
                slug=p_data['slug'],
                defaults={
                    'name': p_data['name'],
                    'meta_title': f"{p_data['name']} - Luxury Bedding | BeddingOrchid",
                    'meta_description': f"Shop export-quality {p_data['name'].lower()} online in Pakistan. 100% combed cotton, anti-pilling weave, and nationwide cash on delivery."
                }
            )
            cat_count += 1
            for c_data in p_data.get('children', []):
                Category.objects.update_or_create(
                    slug=c_data['slug'],
                    defaults={
                        'name': c_data['name'],
                        'parent': parent_cat,
                        'meta_title': f"{c_data['name']} - Luxury Bedding | BeddingOrchid",
                        'meta_description': f"Buy {c_data['name'].lower()} online in Pakistan with BeddingOrchid. Premium long-staple cotton and 7-day easy exchange guarantee."
                    }
                )
                cat_count += 1
        self.stdout.write(self.style.SUCCESS(f"[OK] Initialized {cat_count} Bedding Taxonomy Categories"))

        # 4. Standard Bedding Sizes
        sizes_data = [
            ('King', '96 x 100 in (244 x 254 cm)', 1),
            ('Super King', '102 x 108 in (259 x 274 cm)', 2),
            ('Queen', '90 x 100 in (228 x 254 cm)', 3),
            ('Single', '60 x 90 in (152 x 228 cm)', 4),
            ('Standard Pillow', '19 x 29 in (48 x 74 cm)', 5),
        ]
        for name, dims, order in sizes_data:
            Size.objects.update_or_create(
                name=name,
                defaults={'dimensions': dims, 'sort_order': order}
            )
        self.stdout.write(self.style.SUCCESS(f"[OK] Initialized {len(sizes_data)} Standard Sizes"))

        # 5. Fabric Colors
        colors_data = [
            ('Crisp White', '#FFFFFF'),
            ('Slate Navy', '#1E293B'),
            ('Charcoal Grey', '#374151'),
            ('Warm Terracotta', '#C25E38'),
            ('Soft Sage Green', '#4D7C0F'),
            ('Desert Sand', '#E7DEC8'),
            ('Blush Rose', '#BE7B72'),
            ('Powder Blue', '#8EAFB2'),
        ]
        for name, hex_code in colors_data:
            Color.objects.update_or_create(
                name=name,
                defaults={'hex_code': hex_code}
            )
        self.stdout.write(self.style.SUCCESS(f"[OK] Initialized {len(colors_data)} Fabric Color Swatches"))

        # 6. Policy & CMS Pages
        pages_data = [
            {
                'title': 'About Us',
                'slug': 'about-us',
                'content': """
                <h2 class="text-2xl font-serif font-bold text-stone-900 mb-4">Artisan Bedding, Crafted for Serene Sleep</h2>
                <p class="mb-4 text-stone-700 leading-relaxed">Founded in the heart of Pakistan's rich textile heritage, BeddingOrchid was created to redefine bedroom luxury. We believe that restful sleep is essential for a peaceful life, and that your bed should feel like a sanctuary.</p>
                <p class="mb-4 text-stone-700 leading-relaxed">Every sheet, duvet, and pillow in our collection is crafted with long-staple combed cotton, sustainably dyed, and inspected by master weavers. From hotel-grade 600 thread count sateen to breathable washed linen, our fabrics offer an ultra-soft touch that improves with every wash.</p>
                <div class="my-6 grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="p-6 bg-stone-50 rounded-xl border border-stone-200 text-center">
                        <span class="text-3xl mb-2 block">🌿</span>
                        <h4 class="font-bold text-stone-900 mb-1">100% Combed Cotton</h4>
                        <p class="text-sm text-stone-600">Zero synthetic blends, pure natural breathability.</p>
                    </div>
                    <div class="p-6 bg-stone-50 rounded-xl border border-stone-200 text-center">
                        <span class="text-3xl mb-2 block">🚚</span>
                        <h4 class="font-bold text-stone-900 mb-1">Nationwide COD</h4>
                        <p class="text-sm text-stone-600">Delivered safely to over 300+ cities across Pakistan.</p>
                    </div>
                    <div class="p-6 bg-stone-50 rounded-xl border border-stone-200 text-center">
                        <span class="text-3xl mb-2 block">✨</span>
                        <h4 class="font-bold text-stone-900 mb-1">7-Day Easy Exchange</h4>
                        <p class="text-sm text-stone-600">Hassle-free size and color exchanges if you change your mind.</p>
                    </div>
                </div>
                """
            },
            {
                'title': 'Return & Exchange Policy',
                'slug': 'returns-exchanges',
                'content': """
                <h2 class="text-2xl font-serif font-bold text-stone-900 mb-4">7-Day Easy Return & Exchange Guarantee</h2>
                <p class="mb-4 text-stone-700">At BeddingOrchid, your satisfaction is our highest priority. If you are not completely in love with your bedding, you can request an exchange or return within <strong>7 days</strong> of delivery.</p>
                <h3 class="text-lg font-bold text-stone-900 mb-2">Conditions for Return:</h3>
                <ul class="list-disc pl-5 mb-4 space-y-1 text-stone-700">
                    <li>Items must be unwashed, unused, and in their original packaging with tags intact.</li>
                    <li>Exchange for a different size or color is free of extra service charges; only courier pickup fees apply.</li>
                    <li>If an item is damaged or defective upon arrival, we replace it completely free of charge.</li>
                </ul>
                <h3 class="text-lg font-bold text-stone-900 mb-2">How to Request an Exchange:</h3>
                <p class="text-stone-700">Simply message our customer support team on WhatsApp at <strong>+92 300 1234567</strong> with your order number and parcel photos.</p>
                """
            },
            {
                'title': 'Shipping & Delivery',
                'slug': 'shipping-delivery',
                'content': """
                <h2 class="text-2xl font-serif font-bold text-stone-900 mb-4">Fast Nationwide Shipping Across Pakistan</h2>
                <p class="mb-4 text-stone-700 leading-relaxed">We ship to over 300 cities and rural areas nationwide with trusted courier partners including Trax, Leopards, and Call Courier.</p>
                <ul class="list-disc pl-5 mb-4 space-y-1 text-stone-700">
                    <li><strong>Standard Delivery:</strong> 2 to 4 business days for major cities (Karachi, Lahore, Islamabad, Rawalpindi, Faisalabad).</li>
                    <li><strong>Free Shipping:</strong> Automatically applied to all orders above Rs. 4,000.</li>
                    <li><strong>Cash on Delivery (COD):</strong> Available nationwide with SMS order confirmation.</li>
                </ul>
                """
            },
            {
                'title': 'Privacy Policy',
                'slug': 'privacy-policy',
                'content': "<h2 class='text-2xl font-serif font-bold text-stone-900 mb-4'>Privacy Policy</h2><p class='text-stone-700'>We respect your privacy and protect your contact and shipping details. We do not sell your personal data to third parties.</p>"
            },
            {
                'title': 'Terms & Conditions',
                'slug': 'terms-conditions',
                'content': "<h2 class='text-2xl font-serif font-bold text-stone-900 mb-4'>Terms of Service</h2><p class='text-stone-700'>By purchasing from BeddingOrchid, you agree to our delivery, payment, and exchange terms outlined across our platform.</p>"
            }
        ]
        for p in pages_data:
            Page.objects.update_or_create(slug=p['slug'], defaults=p)
        self.stdout.write(self.style.SUCCESS(f"[OK] Initialized {len(pages_data)} CMS Policy Pages"))

        # Clear cache
        cache.clear()
        self.stdout.write(self.style.SUCCESS("=== Production Baseline Ready! (0 dummy products created) ==="))

