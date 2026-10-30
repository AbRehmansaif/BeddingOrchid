import os
import shutil
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files import File
from apps.catalog.models import Category, Product, ProductImage, ProductVariant, Size, Color, Tag

class Command(BaseCommand):
    help = "Seed the Men's Quilted Leather Puffer Jacket with Fur Collar into BeddingOrchid"

    def handle(self, *args, **options):
        self.stdout.write("=== Seeding Men's Leather Puffer Jacket ===")

        # 1. Category
        category, created = Category.objects.get_or_create(
            name="Men's Leather Jackets",
            defaults={
                'slug': 'mens-leather-jackets',
                'description': "Premium winter outerwear for men. Quilted leather puffer jackets, biker jackets, and cold-weather essentials designed for comfort, warmth, and effortless masculine style.",
                'is_active': True,
                'show_in_menu': True,
                'show_on_home': True,
                'meta_title': "Men's Leather Jackets Online Pakistan | Quilted Winter Outerwear",
                'meta_description': "Shop premium men's leather puffer jackets with fur collar online in Pakistan. Windproof, thermal insulated with nationwide Cash on Delivery.",
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"[OK] Created Category: {category.name}"))
        else:
            self.stdout.write(f"[INFO] Category already exists: {category.name}")

        # 2. Color
        color, _ = Color.objects.get_or_create(
            name="Jet Black",
            defaults={
                'hex_code': '#111111',
            }
        )
        self.stdout.write(self.style.SUCCESS(f"[OK] Color: {color.name}"))

        # 3. Sizes with measurements from chart
        size_specs = [
            ("XS", 'Body Chest 32-34", Jacket Chest 40", Shoulder 17.5", Length 25", Sleeve 24"', 1),
            ("S", 'Body Chest 35-36", Jacket Chest 42", Shoulder 18.0", Length 26", Sleeve 24.5"', 2),
            ("M", 'Body Chest 37-38", Jacket Chest 44", Shoulder 18.5", Length 27", Sleeve 25.0"', 3),
            ("L", 'Body Chest 39-40", Jacket Chest 46", Shoulder 19.0", Length 28", Sleeve 25.5"', 4),
            ("XL", 'Body Chest 41-42", Jacket Chest 48", Shoulder 19.5", Length 29", Sleeve 26.0"', 5),
            ("2XL", 'Body Chest 43-44", Jacket Chest 50", Shoulder 20.0", Length 30", Sleeve 26.5"', 6),
        ]
        
        size_objs = []
        for name, dim, order in size_specs:
            s_obj, _ = Size.objects.get_or_create(
                name=name,
                defaults={
                    'dimensions': dim,
                    'sort_order': order,
                }
            )
            # update dimensions in case it existed with different values
            s_obj.dimensions = dim
            s_obj.sort_order = order
            s_obj.save()
            size_objs.append(s_obj)
        self.stdout.write(self.style.SUCCESS(f"[OK] Configured 6 Apparel Sizes (XS - 2XL)"))

        # 4. Tags
        tag_names = ["Leather Jacket", "Puffer Jacket", "Winter 2026", "Men's Fashion", "Fur Collar", "Windproof Outerwear"]
        tag_objs = []
        for tname in tag_names:
            t_obj, _ = Tag.objects.get_or_create(name=tname)
            tag_objs.append(t_obj)

        # 5. Product Descriptions
        short_desc = (
            "Elevate your winter wardrobe with this iconic Men's Quilted Leather Puffer Bomber Jacket. "
            "Crafted with a supple windproof leather exterior, ultra-soft plush faux-shearling collar, "
            "and horizontal channel quilting for maximum cold-weather insulation without excessive bulk."
        )

        detailed_desc = """
<h3>The Ultimate Statement Piece for the Pakistani Winter</h3>
<p>
Engineered for men who refuse to compromise between razor-sharp style and cold-weather functionality. 
This <strong>Quilted Leather Puffer Jacket with Plush Shearling Fur Collar</strong> combines the bold silhouette of an aviator bomber 
with the thermal heat-retention of a premium quilted puffer.
</p>

<h4>Key Craftsmanship & Design Features:</h4>
<ul>
  <li><strong>Supple Wind-Resistant Exterior:</strong> Premium soft-touch weather-resistant faux leather engineered to shield against biting northern winter winds, rain sprays, and morning fog.</li>
  <li><strong>Plush Faux-Fur Collar:</strong> High-density, ultra-soft black shearling collar cradles your neck in total warmth while commanding attention.</li>
  <li><strong>Thermal Horizontal Channel Quilting:</strong> High-loft synthetic insulation distributed evenly to trap body heat without creating an unmanageable bulky look.</li>
  <li><strong>Heavy-Duty Front Metal Zipper:</strong> Smooth-gliding industrial metal zipper designed for years of daily winter use.</li>
  <li><strong>Twin Zippered Hand Pockets:</strong> Ergonomically angled side pockets with secure zippers to safeguard your smartphone, wallet, keys, and keep your hands warm.</li>
  <li><strong>Elastic Ribbed Cuffs & Hem:</strong> Snug-fitting ribbed knit waistband and cuffs seal out cold drafts and ensure the jacket sits neatly on your waist.</li>
</ul>

<h4>How to Style It:</h4>
<p>
Pair it with a dark turtleneck knit, tailored charcoal trousers, and Chelsea boots for an executive evening look, or dress it down with a crisp white tee, washed denim jeans, and sneakers for a casual weekend vibe.
</p>

<h4>Size & Fit Guide (Inches):</h4>
<table border="1" cellpadding="8" style="width:100%; border-collapse:collapse; text-align:center; margin: 15px 0;">
  <thead style="background-color: #111827; color: #ffffff;">
    <tr>
      <th>Size</th>
      <th>Body Chest Fit</th>
      <th>Jacket Chest</th>
      <th>Shoulder</th>
      <th>Front Length</th>
      <th>Sleeve Length</th>
    </tr>
  </thead>
  <tbody>
    <tr><td><strong>XS</strong></td><td>32" - 34"</td><td>40"</td><td>17.5"</td><td>25"</td><td>24"</td></tr>
    <tr><td><strong>S</strong></td><td>35" - 36"</td><td>42"</td><td>18.0"</td><td>26"</td><td>24.5"</td></tr>
    <tr><td><strong>M</strong></td><td>37" - 38"</td><td>44"</td><td>18.5"</td><td>27"</td><td>25"</td></tr>
    <tr><td><strong>L</strong></td><td>39" - 40"</td><td>46"</td><td>19.0"</td><td>28"</td><td>25.5"</td></tr>
    <tr><td><strong>XL</strong></td><td>41" - 42"</td><td>48"</td><td>19.5"</td><td>29"</td><td>26"</td></tr>
    <tr><td><strong>2XL</strong></td><td>43" - 44"</td><td>50"</td><td>20.0"</td><td>30"</td><td>26.5"</td></tr>
  </tbody>
</table>
<p><small><em>*All measurements are in inches. If you prefer to wear thick hoodies underneath, we recommend sizing up one size.</em></small></p>

<h4>Package Includes & Guarantee:</h4>
<ul>
  <li>1x Men's Quilted Leather Puffer Jacket (Jet Black)</li>
  <li>1x Premium Non-Woven Dust Protection Zipper Bag</li>
  <li>7-Day Hassle-Free Size Exchange & Nationwide Cash on Delivery</li>
</ul>
""".strip()

        product, p_created = Product.objects.get_or_create(
            slug='mens-quilted-leather-puffer-jacket-black',
            defaults={
                'name': "Men's Quilted Leather Puffer Jacket with Plush Fur Collar — Jet Black",
                'sku_prefix': 'MLJ-PUF-BLK',
                'category': category,
                'material': 'Weatherproof Matte PU Leather with High-Loft Thermal Filling',
                'thread_count': 'Windproof Shell | Faux Fur Collar | Ribbed Hem & Cuffs',
                'pieces_included': "1x Men's Quilted Leather Jacket + 1x Protective Garment Cover",
                'care_instructions': "Wipe clean with a damp cloth or soft sponge. Do not machine wash or dry clean. Hang on wide-padded hanger away from direct sunlight.",
                'short_description': short_desc,
                'description': detailed_desc,
                'base_price': Decimal('6990.00'),
                'compare_at_price': Decimal('10990.00'),
                'is_active': True,
                'is_featured': True,
                'is_best_seller': True,
                'is_new': True,
                'cod_available': True,
                'warranty_days': 7,
                'meta_title': "Men's Leather Puffer Jacket with Fur Collar - Black | Buy Online Pakistan",
                'meta_description': "Buy Men's Quilted Leather Puffer Jacket with Plush Fur Collar in Pakistan at Rs. 6,990. Thermal warmth, windproof finish, and Cash on Delivery with open parcel policy.",
            }
        )

        product.tags.set(tag_objs)
        self.stdout.write(self.style.SUCCESS(f"[OK] Product: {product.name} (PKR {product.base_price})"))

        # 6. Images
        static_img_dir = os.path.join(settings.BASE_DIR, 'static', 'images', 'products', 'leather-jacket')
        media_prod_dir = os.path.join(settings.MEDIA_ROOT, 'products')
        os.makedirs(media_prod_dir, exist_ok=True)

        image_files = [
            ('leather-puffer-jacket-fur-collar-1.jpg', "Men's Quilted Leather Puffer Jacket Fur Collar Side Angle View", True, 1),
            ('leather-puffer-jacket-fur-collar-2.jpg', "Men's Black Leather Puffer Jacket Front View Model Shot", False, 2),
            ('leather-puffer-jacket-fur-collar-3.jpg', "Men's Quilted Leather Bomber Jacket Back View", False, 3),
            ('leather-puffer-jacket-size-chart.jpg', "Men's Leather Puffer Jacket Official Size Chart", False, 4),
        ]

        # Clear existing images for this product to avoid duplicates
        ProductImage.objects.filter(product=product).delete()

        created_images = []
        for fname, alt, is_prim, s_order in image_files:
            src_path = os.path.join(static_img_dir, fname)
            if os.path.exists(src_path):
                dest_filename = f"leather_jacket_{fname}"
                dest_path = os.path.join(media_prod_dir, dest_filename)
                shutil.copyfile(src_path, dest_path)
                
                rel_path = f"products/{dest_filename}"
                p_img = ProductImage.objects.create(
                    product=product,
                    image=rel_path,
                    alt_text=alt,
                    is_primary=is_prim,
                    sort_order=s_order
                )
                created_images.append(p_img)
                self.stdout.write(self.style.SUCCESS(f"  + Attached image: {fname} (Primary: {is_prim})"))

        # 7. Variants (XS to 2XL)
        ProductVariant.objects.filter(product=product).delete()
        for s in size_objs:
            sku = f"MLJ-BLK-{s.name}"
            ProductVariant.objects.create(
                product=product,
                size=s,
                color=color,
                sku=sku,
                price=Decimal('6990.00'),
                compare_at_price=Decimal('10990.00'),
                stock_quantity=25,
                is_active=True,
                weight_grams=1400,
                image=created_images[0] if created_images else None
            )
            self.stdout.write(f"  + Created variant: Size {s.name} (SKU: {sku}) - Rs. 6,990")

        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] Leather Puffer Jacket fully seeded with images, variants, and SEO!"))
