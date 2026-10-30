from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from mptt.models import MPTTModel, TreeForeignKey
from apps.core.models import TimeStampedModel
from decimal import Decimal

class Category(MPTTModel, TimeStampedModel):
    """
    Hierarchical nested categories for Bedding and Home Textiles
    (e.g. Bed Sheets -> Fitted Sheets, Luxury Sets; Duvet Covers -> Embroidered, Solid).
    """
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    parent = TreeForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children', db_index=True
    )
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    banner_image = models.ImageField(upload_to='categories/banners/', blank=True, null=True)
    description = models.TextField(blank=True, help_text='Rich description for SEO and category header')
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    show_in_menu = models.BooleanField(default=True, help_text='Display in main mega menu')
    show_on_home = models.BooleanField(default=True, help_text='Display on homepage category grid')

    # SEO Fields
    meta_title = models.CharField(max_length=120, blank=True)
    meta_description = models.CharField(max_length=200, blank=True)
    canonical_url = models.URLField(blank=True)

    class MPTTMeta:
        order_insertion_by = ['sort_order', 'name']

    class Meta:
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.meta_title:
            self.meta_title = f"{self.name} - Luxury Bedding | BeddingOrchid"
        if not self.meta_description:
            self.meta_description = f"Shop premium {self.name.lower()} online in Pakistan. Experience unmatched softness, vibrant colors, and fast cash on delivery delivery."
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        # Category path
        ancestors = self.get_ancestors(include_self=True)
        path = "/".join([a.slug for a in ancestors])
        return reverse('catalog:category_detail', kwargs={'category_path': path})

    def __str__(self):
        return self.name


class Tag(TimeStampedModel):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Size(TimeStampedModel):
    """
    Bedding sizes: Single, Double, Queen, King, Super King, Standard Pillow, etc.
    """
    name = models.CharField(max_length=60, help_text='e.g. King, Queen, Single, Standard Pillow')
    dimensions = models.CharField(max_length=100, blank=True, help_text='e.g. 96 x 100 in (244 x 254 cm)')
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        if self.dimensions:
            return f"{self.name} ({self.dimensions})"
        return self.name


class Color(TimeStampedModel):
    """
    Bedding fabric colors and swatches.
    """
    name = models.CharField(max_length=60, help_text='e.g. Slate Navy, Crisp Ivory, Sage Green')
    hex_code = models.CharField(max_length=10, default='#FFFFFF', help_text='Hex color code e.g. #1E293B')
    swatch_image = models.ImageField(upload_to='swatches/', blank=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    """
    Primary Product Model for Bedding & Home Textiles.
    """
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=265, unique=True)
    sku_prefix = models.CharField(max_length=50, blank=True, help_text='e.g. BS-SAT-01')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    additional_categories = models.ManyToManyField(Category, blank=True, related_name='secondary_products')
    
    # Textile specs
    material = models.CharField(max_length=120, default='100% Combed Cotton Percale', help_text='e.g. Egyptian Sateen, Washed Linen, 100% Cotton Percale')
    thread_count = models.CharField(max_length=60, default='400 Thread Count', help_text='e.g. 400 TC, 600 TC Hotel Luxury')
    pieces_included = models.CharField(max_length=255, default='1 Fitted Sheet + 1 Flat Sheet + 2 Pillowcases', help_text='What is in the box?')
    care_instructions = models.TextField(default='Machine wash warm with like colors. Do not bleach. Tumble dry gentle. Warm iron if needed.')
    
    short_description = models.TextField(help_text='Brief summary shown near price and in Meta tags')
    description = models.TextField(help_text='Detailed product story and textile benefits')

    base_price = models.DecimalField(max_digits=12, decimal_places=2, help_text='Starting or standard selling price')
    compare_at_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text='Original strike-through price')

    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_best_seller = models.BooleanField(default=False, db_index=True)
    is_new = models.BooleanField(default=True, db_index=True)
    cod_available = models.BooleanField(default=True, help_text='Is Cash on Delivery allowed for this product?')
    warranty_days = models.PositiveIntegerField(default=7, help_text='Days for easy exchange / return')

    tags = models.ManyToManyField(Tag, blank=True, related_name='products')
    
    # SEO
    meta_title = models.CharField(max_length=150, blank=True)
    meta_description = models.CharField(max_length=220, blank=True)
    og_image = models.ImageField(upload_to='seo/products/', blank=True, null=True)

    class Meta:
        ordering = ['-is_featured', '-is_best_seller', '-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.meta_title:
            self.meta_title = f"{self.name} | Premium Bedding in Pakistan"
        if not self.meta_description:
            desc = self.short_description or self.description[:150]
            self.meta_description = f"Buy {self.name} online. {desc[:120]}... Cash on delivery & fast nationwide shipping."
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('catalog:product_detail', kwargs={'slug': self.slug})

    @property
    def discount_percent(self):
        if self.compare_at_price and self.compare_at_price > self.base_price:
            saving = self.compare_at_price - self.base_price
            return int(round((saving / self.compare_at_price) * 100))
        return 0

    @property
    def primary_image(self):
        img = self.images.filter(is_primary=True).first()
        if not img:
            img = self.images.first()
        return img

    @property
    def in_stock(self):
        variants = self.variants.filter(is_active=True)
        if variants.exists():
            return any(v.stock_quantity > 0 for v in variants)
        return True

    @property
    def average_rating(self):
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            return round(reviews.aggregate(models.Avg('rating'))['rating__avg'] or 5.0, 1)
        return 5.0

    @property
    def reviews_count(self):
        return self.reviews.filter(is_approved=True).count()

    @property
    def stars_display(self):
        val = float(self.average_rating)
        full_stars = int(val)
        has_half = (val - full_stars) >= 0.25
        empty_stars = 5 - full_stars - (1 if has_half else 0)
        return ('★' * full_stars) + ('½' if has_half else '') + ('☆' * max(0, empty_stars))

    def __str__(self):
        return self.name


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']

    def save(self, *args, **kwargs):
        if not self.alt_text and self.product:
            self.alt_text = f"{self.product.name} - Luxury Bedding Textile"
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Image for {self.product.name}"


class ProductVariant(TimeStampedModel):
    """
    Specific variant of a product combining Size + Color.
    Holds SKU, stock levels, and price overrides.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name='variants', null=True, blank=True)
    color = models.ForeignKey(Color, on_delete=models.PROTECT, related_name='variants', null=True, blank=True)
    sku = models.CharField(max_length=64, unique=True, db_index=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text='Leave empty to use product base price')
    compare_at_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=20)
    is_active = models.BooleanField(default=True, db_index=True)
    weight_grams = models.PositiveIntegerField(default=1200, help_text='Weight in grams for shipping calculations')
    image = models.ForeignKey(ProductImage, on_delete=models.SET_NULL, null=True, blank=True, related_name='variant_images')

    class Meta:
        unique_together = ('product', 'size', 'color')
        ordering = ['size__sort_order', 'color__name']

    @property
    def effective_price(self):
        return self.price if self.price is not None else self.product.base_price

    @property
    def effective_compare_at_price(self):
        if self.compare_at_price is not None:
            return self.compare_at_price
        return self.product.compare_at_price

    @property
    def discount_percent(self):
        comp = self.effective_compare_at_price
        eff = self.effective_price
        if comp and comp > eff:
            return int(round(((comp - eff) / comp) * 100))
        return 0

    @property
    def is_in_stock(self):
        return self.stock_quantity > 0

    def __str__(self):
        parts = [self.product.name]
        if self.size:
            parts.append(str(self.size.name))
        if self.color:
            parts.append(str(self.color.name))
        return " - ".join(parts)


class QuantityDiscount(TimeStampedModel):
    """
    Multi-buy / bundle savings: e.g. Buy 2 get 5% off, Buy 3 get 10% off.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='quantity_discounts', null=True, blank=True)
    min_quantity = models.PositiveIntegerField(default=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)

    class Meta:
        ordering = ['min_quantity']

    def __str__(self):
        prod = self.product.name if self.product else "All Products"
        return f"{prod}: Buy {self.min_quantity}+ get {self.discount_percentage}% off"
