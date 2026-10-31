# OpsPilot: Seeded Mock Data Errors

This catalog lists all deliberate validation errors and soft anomalies seeded in the mock datasets (`app/mock_data/`), along with the offending rows and the corresponding rule IDs. Automated tests assert that 100% of these seeded errors are detected.

---

## 1. Invoices Dataset (`invoices.csv`)

| Row Identifier | Field | Offending Value | Rule ID | Severity | Description |
|---|---|---|---|---|---|
| `INV-102` | `email` | `ravi@@example` | `EML-01` | Error | Joined customer (`CUST-002`) has a malformed email address. |
| `INV-103` (2nd occurrence) | `invoice_id` | `INV-103` | `DUP-01` | Error | Duplicate primary invoice key within dataset. |
| `INV-104` | `amount` | `950000` | `AMT-ANOM-01` | Warning/Anomaly | Outlier amount roughly 105x customer's median normal invoice (~₹9,000). |
| `INV-105` | `email` | `""` (blank) | `REQ-01` | Error | Joined customer (`CUST-005`) is missing mandatory email address. |
| `INV-106` | `amount` | `-3000` | `NUM-01` | Error | Negative invoice amount. |
| `INV-110` | `due_date` | `2099-01-01` | `DAT-01` | Error | Sane date window exceeded (greater than today + 365 days). |
| `INV-115` | `customer_id` | `CUST-999` | `REF-01` | Error | Orphan foreign reference: customer ID does not exist in `customers`. |

*Note on due dates:* At load time, relative offsets like `OFFSET:-25` are converted dynamically relative to current UTC date so invoices remain consistently overdue for live demonstrations.

---

## 2. Customers Dataset (`customers.csv`)

| Row Identifier | Field | Offending Value | Rule ID | Severity | Description |
|---|---|---|---|---|---|
| `CUST-002` | `email` | `ravi@@example` | `EML-01` | Error | Invalid email format (double @). |
| `CUST-005` | `email` | `""` (empty) | `REQ-01` | Error | Missing required customer email address. |
| `CUST-008` | `phone` | `12345` | `PHN-01` | Warning | Invalid Indian phone number format. |
| `CUST-004` & `CUST-014` | `name` | `Kiran Sharma` / `Kiran Patel` | `AMB-NAME-01` | Warning/Anomaly | Ambiguous customer name: multiple records share first name "Kiran". |

---

## 3. Orders Dataset (`orders.csv`)

| Row Identifier | Field | Offending Value | Rule ID | Severity | Description |
|---|---|---|---|---|---|
| `ORD-205` | `qty`, `price` | `-2`, `-900` | `NUM-01` | Error | Negative order quantity and price. |
| `ORD-210` | `customer_id` | `""` (empty) | `REQ-01` | Error | Missing required customer reference. |
| `ORD-215` (2nd occurrence) | `order_id` | `ORD-215` | `DUP-01` | Error | Duplicate order identifier. |

---

## 4. Bookings Dataset (`bookings.csv`)

| Row Identifier | Field | Offending Value | Rule ID | Severity | Description |
|---|---|---|---|---|---|
| `BK-302` & `BK-303` | `resource`, `slot_start`, `slot_end` | `Delivery Van A` (10:00-12:00 vs 11:00-13:00) | `CNF-01` | Error | Scheduling conflict: overlapping bookings for the same resource. |
