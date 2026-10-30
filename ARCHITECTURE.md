# LinenCraft Studio Architecture & Scaling Guide

## 1. High-Level Architecture Diagram

```
                                [ Cloudflare CDN & Edge Cache ]
                                               │
                                               ▼
                                      [ Nginx Reverse Proxy ]
                                               │
                    ┌──────────────────────────┴──────────────────────────┐
                    ▼                                                     ▼
           [ Gunicorn Web App 1 ]                                [ Gunicorn Web App N ]
           (Django 5.x LTS ASGI/WSGI)                            (Django 5.x LTS ASGI/WSGI)
                    │                                                     │
                    ├──────────────────────────┬──────────────────────────┤
                    │                          │                          │
                    ▼                          ▼                          ▼
          [ PostgreSQL 15+ ]            [ Redis Cluster ]         [ Celery Workers & Beat ]
          - pg_trgm Search              - Page Cache              - Meta CAPI Background Tasks
          - Row-locking select_for_update - Session Storage         - Order Notification Emails
          - Keyset Pagination           - Cache-Invalidation      - Courier Label Generation
```

---

## 2. Django Apps & Separation of Concerns

- **`apps.core`**: `TimeStampedModel`, singleton `SiteSettings`, `TrackingMiddleware` (captures UTMs, `_fbp`, `fbclid` -> `_fbc`), currency formatters, and global context processors.
- **`apps.accounts`**: Custom `User` model with phone or email authentication, `Address` model, `Wishlist` & `WishlistItem`.
- **`apps.catalog`**: Tree-structured nested `Category` (MPTT), `Size` (with physical dimensions), `Color` (with hex swatches), `Product`, `ProductImage`, `ProductVariant` (holds SKU and stock levels), `QuantityDiscount`.
- **`apps.inventory`**: `StockMovement` audit logs and atomic stock services (`select_for_update()` inside `transaction.atomic()`).
- **`apps.cart`**: Session-backed and DB-backed shopping carts. Recalculates all line prices and discounts dynamically from the database on every request.
- **`apps.orders`**: Complete COD order pipeline (`Pending` &rarr; `Confirmed` &rarr; `Processing` &rarr; `Packed` &rarr; `Dispatched` &rarr; `Delivered`), order state machine transition rules, editable address in admin, courier tracking links, and printable invoices.
- **`apps.promotions`**: `SaleTag` overlay badges on images (`HOT SELLER`, `-30%`, `BESTSELLER`), `FlashSale` with timers, `Coupon` discount engine, and `Banner` hero slides.
- **`apps.reviews`**: Moderated customer reviews with star ratings and verified buyer tags.
- **`apps.pages`**: CMS Policy pages (`About Us`, `Privacy Policy`, `Shipping Policy`, `Size Guide`, `Care Guide`, `FAQ` with JSON-LD schema) and `ContactMessage`.
- **`apps.seo`**: Dynamic `robots.txt`, `sitemap.xml`, 301 `Redirect` middleware, and SEO health audit tools.
- **`apps.marketing`**: Meta Pixel browser tracking, server-side Meta Conversions API (CAPI) with SHA-256 hashing and shared `event_id` deduplication, XML and CSV product catalog feeds (`/feeds/meta-catalog.xml`).
- **`apps.notifications`**: Pluggable email, SMS, and WhatsApp notification services and Celery tasks.

---

## 3. Data Integrity & Concurrency Rules

1. **Race-Condition-Free Stock Reservation**:
   When orders are placed, the inventory service acquires a database row-level lock using `select_for_update()` on `ProductVariant`. This prevents negative stock and overselling when hundreds of shoppers purchase the same bed sheet simultaneously.
2. **Snapshot Integrity**:
   `Order` and `OrderItem` store frozen snapshots of customer name, phone, address, unit prices, SKU, size, and color. Subsequent changes to catalog prices or sizes never alter past historical orders.
3. **Audit History & Transitions**:
   `OrderStatusHistory` logs every transition, the staff member who made it, and the timestamp. The `OrderStateMachine` disallows illegal jumps (e.g. `pending` cannot jump directly to `delivered`).
4. **Editable Shipping Address**:
   Customer addresses are stored directly on the `Order` record with full editing permission in the Django admin to support phone-based address corrections before dispatch.

---

## 4. Scaling Strategy for 10,000 Concurrent Users

1. **Stateless Web Tier**: Gunicorn web workers run statelessly behind Nginx. Sessions and cache are stored in Redis.
2. **Read Replica Ready**: Database queries utilize `select_related()` and `prefetch_related()` throughout, eliminating N+1 queries.
3. **Multi-Layered Caching**:
   - Edge Cache (Cloudflare): HTML edge caching of anonymous Home, Category, and Static pages with cache bypass cookies for logged-in or cart-bearing visitors.
   - Redis Fragment Cache: Navigation mega-menus and category trees are cached in Redis and invalidated via Django model signals.
4. **Async Offloading via Celery**:
   Slow external I/O (Meta Conversions API Graph calls, transactional emails, and courier booking notifications) are processed asynchronously in background Celery queues without blocking HTTP response times.
5. **Load Testing Target**:
   With the included `locustfile.py`, simulate 10,000 simulated shoppers with a target P95 latency of < 500ms on cached browse views and < 1.5s on checkout completion.
