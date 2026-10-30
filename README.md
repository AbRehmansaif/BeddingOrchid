# LinenCraft Studio — Django Bedding & Home Textile E-Commerce

A modern, production-ready, SEO-first Django e-commerce platform crafted for **bedding and home textile brands** (luxury bed sheet sets, duvet/quilt covers, comforters, memory foam pillows, mattress protectors, and living accessories).

Built with **Django 5.x LTS**, **PostgreSQL / SQLite**, **Redis**, **Celery**, and **Tailwind CSS**. Optimized for the **Cash on Delivery (COD)** market and **Meta (Facebook/Instagram) Ads** traffic.

---

## 🚀 Key Features

- **SEO & Performance First**: Semantic HTML5, structured JSON-LD schemas (`Product`, `Organization`, `WebSite`, `FAQPage`, `BreadcrumbList`), dynamic `sitemap.xml`, and clean `robots.txt`.
- **Bedding Attribute Architecture**: Multi-level category hierarchy with `django-mptt`, bedding dimensions in inches/cm, and fabric color swatches.
- **Race-Safe Stock & Concurrency**: Row-level database locks (`select_for_update()`) prevent overselling under high concurrency.
- **COD Single-Page Checkout**: Frictionless 1-step checkout with instant account creation or guest-friendly login.
- **Full-Featured Admin Operations**:
  - Live order pipeline: `Pending` &rarr; `Confirmed` &rarr; `Processing` &rarr; `Packed` &rarr; `Dispatched` &rarr; `Delivered`.
  - **Editable customer shipping address** directly in Django Admin.
  - Printable **Thermal & A4 Invoices / Packing Slips**.
  - One-click **CSV Export for Courier Upload** (compatible with TCS, Trax, Leopards, and PostEx).
- **Meta Ads & Conversions API (CAPI)**:
  - Browser Meta Pixel integration (`PageView`, `ViewContent`, `AddToCart`, `Purchase`).
  - Server-side Meta Conversions API with SHA-256 data hashing and shared `event_id` deduplication.
  - Automated XML & CSV product catalog feeds (`/feeds/meta-catalog.xml` and `/feeds/meta-catalog.csv`).
  - First-touch and last-touch UTM, `_fbp`, and `fbclid` (`_fbc`) attribution capture.
- **Visual Micro-Interactions**: Image badge overlays (`HOT SELLER`, `-30% OFF`, `BESTSELLER`), AJAX slide-out mini-cart drawer, free shipping progress bar, and floating WhatsApp chat button.

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Framework | Python 3.11+, Django 5.1 LTS |
| Database | PostgreSQL 15+ (Production) / SQLite3 (Zero-Config Dev) |
| Caching & Broker | Redis (Celery Tasks & Page Fragment Caching) |
| Async Workers | Celery & Celery Beat |
| Frontend | Django Templates + Tailwind CSS + Google Fonts |
| Image Generation | Pillow (PIL) |
| Server | Gunicorn behind Nginx / Cloudflare |

---

## 📦 Quick Start (Local Virtual Environment)

### 1. Prerequisites
Ensure you have Python 3.11+ installed.

### 2. Activate Virtual Environment
The virtual environment `.venv` is ready in the repository root:

**On Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Database Migrations
```bash
python manage.py migrate
```

### 5. Seed Demo Bedding Data
Populate your database with 31 luxury bedding products, sizes, colors, variants, images, categories, policy pages, hero banners, and discount coupons:
```bash
python manage.py seed_demo_data
```

### 6. Run the Development Server
```bash
python manage.py runserver 127.0.0.1:8000
```
Visit **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)** in your browser.

---

## 🔑 Default Credentials

- **Admin Portal**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
- **Username**: `admin`
- **Password**: `admin`

---

## 🐳 Docker Deployment

To launch the full production-style stack with PostgreSQL, Redis, Celery, and Gunicorn:

```bash
docker-compose up -d --build
```
Run migrations and seed data inside the container:
```bash
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py seed_demo_data
```

---

## ⚙️ Environment Variables (`.env`)

Configure the following variables in `.env`:

```ini
DEBUG=True
SECRET_KEY=your-production-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

# Database (PostgreSQL in production, SQLite in local dev)
DATABASE_URL=sqlite:///db.sqlite3

# Redis & Celery
REDIS_URL=redis://127.0.0.1:6379/1
CELERY_BROKER_URL=redis://127.0.0.1:6379/0

# Business Rules
BRAND_NAME=LinenCraft Studio
STORE_DOMAIN=localhost:8000
STORE_CURRENCY=PKR
DEFAULT_SHIPPING_FEE=250.00
FREE_SHIPPING_THRESHOLD=4000.00
DEFAULT_COD_FEE=0.00

# Meta Ads Integration
META_PIXEL_ID=your_pixel_id
META_CAPI_ACCESS_TOKEN=your_capi_access_token
META_TEST_EVENT_CODE=
```

---

## 🏷️ Admin Management Guide

### 1. Managing Categories & Mega-Menu
1. Go to **Admin &rarr; Categories**.
2. Click and drag or edit parent-child relationships for unlimited nesting (e.g. *Bed Sheets &rarr; Luxury Sateen Bed Sheets*).
3. Toggle `Show In Menu` to control appearance in the navigation mega-menu.

### 2. Processing Cash on Delivery (COD) Orders
1. Go to **Admin &rarr; Orders**.
2. Orders arrive in **`Pending Confirmation`** status.
3. Call/WhatsApp the customer to verify address details. If the customer gives updated instructions, click into the order and edit the **Shipping Address** fields directly.
4. Use the quick status buttons to transition the order:
   - `Verify & Confirm` &rarr; `Send to Processing` &rarr; `Mark as Packed` &rarr; `Mark Dispatched` &rarr; `Mark Delivered & Paid`.
5. Click **📄 Invoice** on any order to open and print the packing slip.
6. Select multiple orders and choose **Export for Courier Booking (CSV)** to generate a booking spreadsheet for Trax, TCS, Leopards, or PostEx.

---

## 📈 Meta Ads & Dynamic Product Ads (DPA) Setup

1. **Pixel & CAPI**: Add your `META_PIXEL_ID` and `META_CAPI_ACCESS_TOKEN` in SiteSettings or `.env`. The system sends browser Pixel events and asynchronous server-side CAPI events deduplicated with the order reference.
2. **Catalog Feed**:
   - XML Feed URL: `https://yourdomain.com/feeds/meta-catalog.xml`
   - CSV Feed URL: `https://yourdomain.com/feeds/meta-catalog.csv`
   - In Meta Commerce Manager, create a new catalog and select **Data Feed &rarr; Scheduled Feed** pointing to the XML URL.

---

## 🧪 Testing

Run the automated test suite:
```bash
python manage.py test tests
```
All tests verify pricing, stock row-locking, order state transitions, and cart calculations.
