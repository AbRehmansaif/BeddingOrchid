from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from apps.core.models import TimeStampedModel
from apps.core.utils import normalize_phone_pk

class UserManager(BaseUserManager):
    """Custom user manager supporting registration with email or phone."""
    def create_user(self, email=None, phone=None, password=None, **extra_fields):
        if not email and not phone:
            raise ValueError('A user must have either an email address or a phone number.')
        
        if email:
            email = self.normalize_email(email)
        if phone:
            phone = normalize_phone_pk(phone)

        # Set username to email or phone or custom string
        username = extra_fields.pop('username', None)
        if not username:
            username = email or phone

        user = self.model(username=username, email=email, phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if not email and username:
            email = f"{username}@admin.local"
        if not username:
            username = email or 'admin'
        return self.create_user(email=email, username=username, password=password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model for bedding e-commerce.
    Customers can log in with either phone number or email address.
    """
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)
    email = models.EmailField(unique=True, null=True, blank=True, db_index=True)
    is_phone_verified = models.BooleanField(default=False)
    marketing_opt_in = models.BooleanField(default=True)

    objects = UserManager()

    def save(self, *args, **kwargs):
        if self.phone:
            self.phone = normalize_phone_pk(self.phone)
        if not self.full_name:
            self.full_name = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or self.phone or self.email or self.username


class Address(TimeStampedModel):
    """Customer shipping address model."""
    LABEL_CHOICES = (
        ('Home', 'Home'),
        ('Office', 'Office'),
        ('Other', 'Other'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=20, choices=LABEL_CHOICES, default='Home')
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=25)
    address_line1 = models.CharField(max_length=255, help_text='House/Apartment #, Street name, Area')
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, db_index=True)
    province = models.CharField(max_length=100, default='Punjab')
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='Pakistan')
    landmark = models.CharField(max_length=255, blank=True, help_text='Nearby well-known place')
    is_default = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-created_at']

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} - {self.address_line1}, {self.city}"


class Wishlist(TimeStampedModel):
    """User wishlist collection."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wishlist')

    def __str__(self):
        return f"{self.user}'s Wishlist"


class WishlistItem(TimeStampedModel):
    """Product saved in user wishlist."""
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='wishlist_items')

    class Meta:
        unique_together = ('wishlist', 'product')

    def __str__(self):
        return f"{self.wishlist.user} - {self.product.name}"
