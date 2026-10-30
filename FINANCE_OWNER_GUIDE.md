# 💰 Store Owner's Guide: Profit & Finance Dashboard

Welcome to your store's financial headquarters inside Django Admin. This guide explains how to view your real financial numbers, enter costs, import marketing and courier statements, and understand every metric down to the rupee.

---

## 1. Accessing the Dashboard

1. Navigate to: `http://your-domain.com/admin/finance/dashboard/`
2. **Permission Requirement:** Only users with `finance.view_dashboard` permission (such as **Superusers**, **Store Owners**, and **Accountants**) can access the dashboard and view cost/profit figures.
3. Other staff members (such as Customer Support and Warehouse Packers) will NOT see product costs, courier costs, margins, or profit anywhere in the admin.

---

## 2. Reading the Dashboard (Every Number Explained)

### Top Bar Controls
- **Date Presets:** Today, Yesterday, Last 7 Days, Last 30 Days, This Month, Last Month, or a Custom Date Range.
- **Reporting Basis:** Defaults to **Delivered Date** (COD cash is only realised when an order is delivered).
- **Exports:** One-click downloads for **CSV**, **Excel (.xls)**, or **Printable Executive Report (PDF)**.

### Row 1: Key Performance Indicators (KPIs)
- **Net Revenue:** Real cash turnover from delivered orders (Gross Sales minus discounts, customer refunds, plus customer shipping/COD income).
- **COGS (Cost of Goods Sold):** Total supplier/manufacturing cost of units actually delivered (snapshot at the moment of order placement).
- **Gross Profit:** `Net Revenue - COGS`.
- **Ad Spend:** Total money spent across advertising platforms (Meta, Google, TikTok).
- **Courier Expenses:** Forward freight, COD handling fees, and RTO return charges across all dispatched orders.
- **Return Loss:** Cost of items damaged in transit or written off as unsellable.
- **Operating Expenses:** Overheads (salaries, office rent, software, utilities) attributed to the period.
- **True Net Profit:** Real bottom-line profit after deducting ALL product costs, logistics, advertising, returns, and operating expenses.
- **Net Margin %:** `Net Profit ÷ Net Revenue × 100`.
- **Platform ROAS vs Real ROAS:**
  - *Platform ROAS:* Reported by Meta Ads (often inflated because Meta counts orders that later cancel or return).
  - *Real ROAS:* `Actual Delivered Net Revenue ÷ Ad Spend`.
- **Break-even ROAS:** The minimum ROAS required just to cover product and courier costs (`1 ÷ Contribution Margin %`).

---

## 3. How to Enter and Import Product Costs

Costs are tracked per **Product Variant** (e.g. King vs Single, White vs Navy) so profit is accurate regardless of product mix.

1. **In Django Admin:** Go to **Finance & Profit > Variant Costs**.
2. Click **Add Variant Cost** and select the product variant.
3. Enter:
   - **Unit Cost:** Manufacturing or supplier purchase price per piece.
   - **Packaging Cost:** Any variant-specific box or bag cost (optional; falls back to store default Rs 60).
   - **Effective From:** Date from which this cost applies.
4. **Historical Snapshots:** Changing a variant's cost today will **NEVER** rewrite old orders. Old orders maintain their snapshotted cost from the date they were placed.
5. **Bulk Import:** You can import thousands of costs from CSV/Excel using `django-import-export` directly on the Variant Cost list page.

---

## 4. How to Track Advertising Spend

### A. Meta Ads API Automatic Sync
- In `.env` or Django Admin settings, configure `META_ADS_ACCESS_TOKEN` and your **Meta Ad Account ID**.
- A nightly Celery task automatically pulls campaign-level spend, impressions, clicks, and reported purchases, re-checking the last 7 days to account for Meta's attribution adjustments.

### B. CSV Upload (Meta, Google, TikTok)
- Go to: `/admin/finance/adspend/import/`
- Select the platform (**Meta**, **Google**, **TikTok**) and upload your export CSV.
- Foreign currencies (e.g. USD) are automatically converted to PKR using the exchange rate recorded in **Exchange Rates**.

---

## 5. How to Import Courier Statements & Reconcile COD

Couriers provide weekly or monthly statement CSVs (TCS, Leopards, PostEx, Trax, M&P).

1. Go to: `/admin/finance/courier/import/`
2. Select your courier partner.
3. Upload the statement CSV.
4. **Automatic Matching:** The system matches tracking numbers against your store's orders and records:
   - Forward delivery fee
   - COD commission fee
   - Return / RTO charge
   - Fuel surcharge and sales tax
5. **Unmatched Rows:** Any parcel not found in your orders is listed in an unmatched review table for manual audit.
6. **Rate Card Fallback:** If a statement hasn't arrived yet, orders use your **Courier Rate Card** to estimate charges, marked with a yellow `⚠️ ESTIMATED` badge.

---

## 6. How to Process Returns at the Warehouse

When a courier returns an undelivered parcel (RTO) or a customer returns an item:

1. Open the **Returns & RTO Scan Station**: `/admin/finance/returns/receive/`
2. Scan the barcode on the parcel label or type the tracking number / order number.
3. For each item inside the parcel:
   - Check **Sellable** if the item is in pristine condition to return it to active stock inventory.
   - Check **Damaged / Defective** if the packaging or product was ruined. The system logs a damage loss write-off based on the item's cost snapshot.
4. Click **Confirm & Process Return Parcel**. The order status and financials are updated immediately.

---

## 7. How to Enter Operating Expenses

1. Go to **Finance & Profit > Operating Expenses > Add Operating Expense**.
2. Select a category (Salaries, Rent, Software, Influencers, Utilities).
3. If the expense is recurring (e.g. monthly rent of Rs 150,000), check **Is Recurring** and choose **Monthly**. The dashboard will spread the expense smoothly across each day of the month.

---

## 8. Management Commands

- Bulk recalculate all order financials and rebuild daily summaries:
  ```bash
  python manage.py recalculate_financials --rebuild-summaries
  ```
- Recalculate specific date range:
  ```bash
  python manage.py recalculate_financials --from 2026-01-01 --to 2026-01-31
  ```
