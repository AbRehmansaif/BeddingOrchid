from decimal import Decimal
import pytest
from django.test import TestCase, RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth import get_user_model
from apps.core.models import SiteSettings
from apps.catalog.models import Category, Product, Size, Color, ProductVariant
from apps.promotions.models import Coupon
from apps.inventory.services import InventoryService
from apps.cart.services import CartService
from apps.orders.models import Order
from apps.orders.services import OrderStateMachine, OrderService
from apps.marketing.services import MetaConversionsApiService

User = get_user_model()

class BeddingStoreTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site_settings = SiteSettings.get_settings()
        self.site_settings.free_shipping_threshold = Decimal('4000.00')
        self.site_settings.default_shipping_fee = Decimal('250.00')
        self.site_settings.save()

        self.category = Category.objects.create(name="Bed Sheets", slug="bed-sheets")
        self.size_king = Size.objects.create(name="King", dimensions="96x100 in", sort_order=1)
        self.color_navy = Color.objects.create(name="Slate Navy", hex_code="#1E293B")

        self.product = Product.objects.create(
            name="Percale Cotton Bed Sheet",
            slug="percale-cotton-bed-sheet",
            category=self.category,
            base_price=Decimal('3500.00'),
            compare_at_price=Decimal('4500.00'),
            is_active=True
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            size=self.size_king,
            color=self.color_navy,
            sku="LC-TEST-KING-NAVY",
            price=Decimal('3500.00'),
            stock_quantity=20,
            is_active=True
        )

    def test_stock_decrement_and_restore(self):
        """Test atomic inventory deduction and restoration."""
        initial_stock = self.variant.stock_quantity
        InventoryService.decrement_stock(self.variant.id, 2, order_ref="LC-TEST-001")
        
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, initial_stock - 2)

        # Restore stock on cancellation
        InventoryService.restore_stock(self.variant.id, 2, order_ref="LC-TEST-001", reason="cancellation")
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, initial_stock)

    def test_order_state_machine_validations(self):
        """Test order status transition rules."""
        self.assertTrue(OrderStateMachine.can_transition('pending', 'confirmed'))
        self.assertTrue(OrderStateMachine.can_transition('confirmed', 'processing'))
        self.assertTrue(OrderStateMachine.can_transition('processing', 'packed'))
        self.assertTrue(OrderStateMachine.can_transition('packed', 'dispatched'))
        self.assertTrue(OrderStateMachine.can_transition('dispatched', 'delivered'))
        
        # Illegal transitions
        self.assertFalse(OrderStateMachine.can_transition('pending', 'delivered'))
        self.assertFalse(OrderStateMachine.can_transition('delivered', 'processing'))

    def test_coupon_calculation(self):
        """Test percentage and fixed coupon logic."""
        coupon_pct = Coupon.objects.create(
            code="SAVE10",
            discount_type="percentage",
            value=Decimal('10.00'),
            min_order_amount=Decimal('2000.00'),
            is_active=True
        )
        is_valid, _ = coupon_pct.is_valid_for(Decimal('3500.00'))
        self.assertTrue(is_valid)
        discount = coupon_pct.calculate_discount(Decimal('3500.00'))
        self.assertEqual(discount, Decimal('350.00'))

    def test_cart_service_pricing_and_shipping(self):
        """Test dynamic cart subtotal, shipping calculation, and thresholds."""
        request = self.factory.get('/')
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        cart = CartService(request)
        cart.add(self.variant.id, 1)

        # Below 4000 threshold, shipping fee is 250
        self.assertEqual(cart.get_subtotal(), Decimal('3500.00'))
        self.assertEqual(cart.get_shipping_fee(), Decimal('250.00'))
        self.assertEqual(cart.get_grand_total(), Decimal('3750.00'))

        # Add 1 more (total 7000 >= 4000 threshold), shipping becomes FREE
        cart.add(self.variant.id, 1)
        self.assertEqual(cart.get_subtotal(), Decimal('7000.00'))
        self.assertEqual(cart.get_shipping_fee(), Decimal('0.00'))
        self.assertEqual(cart.get_grand_total(), Decimal('7000.00'))
