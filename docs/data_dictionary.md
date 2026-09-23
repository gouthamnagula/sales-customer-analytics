# Data dictionary

## Raw files (`data/raw/`)

### customers.csv
| column | type | notes |
|---|---|---|
| customer_id | text | `CUST-00001` format. Some rows repeated, some lower case / trailing spaces |
| customer_name | text | |
| email | text | some missing, some upper case with leading space |
| city | text | many spellings for the same city (Bangalore / BLR / Bengaluru) |
| segment | text | Retail, SMB, Corporate (sometimes lower case) |
| signup_date | text | mixed formats: `2025-03-14`, `14/03/2025`, `14-Mar-2025` |

### products.csv
| column | type | notes |
|---|---|---|
| product_id | text | `PRD-0001` format |
| product_name | text | |
| category | text | Electronics, Home & Kitchen, Fashion, Personal Care, Stationery, Sports |
| list_price | number | rupees |

### orders.csv (one row per order line)
| column | type | notes |
|---|---|---|
| order_id | text | `SO100001`; an order can have many lines |
| order_date | text | same 3 mixed formats as signup_date |
| customer_id | text | sometimes missing, sometimes not in customer master |
| product_id | text | `PRD-9999` = product not in master |
| quantity | int | negative = return line, 0 = invalid |
| unit_price | text/number | sometimes text like `₹1,299.00` |
| discount_pct | number | 0-100 |
| channel | text | Online / Store / Marketplace with different spellings |

## Warehouse (`data/processed/warehouse.db`)

Star schema, DDL in `sql/schema.sql`.

| table | grain | key columns |
|---|---|---|
| fact_sales | one order line | sales_id, order_id, date_key, customer_key, product_key, quantity, unit_price, discount_pct, line_amount, is_return |
| dim_customer | one customer | customer_key, customer_id, city, region, segment, signup_date |
| dim_product | one product | product_key, product_id, product_name, category, list_price |
| dim_date | one calendar day | date_key (yyyymmdd), month, quarter, year, weekday, is_weekend |
| customer_rfm | one customer | recency_days, frequency, monetary, r/f/m scores, segment |

`line_amount = quantity x unit_price x (1 - discount_pct / 100)` - negative for returns.

## Validation rules (order lines)

Applied in this order, a line gets the first rule it fails:

1. exact duplicate row -> removed (counted separately)
2. `bad_date` - date could not be parsed in any of the 3 formats
3. `missing_customer_id`
4. `unknown_customer` - id not in customer master
5. `unknown_product` - id not in product master
6. `zero_or_bad_quantity` - quantity 0 or not a number
7. `bad_price` - price missing, not a number or <= 0

Rejected lines are written to `reports/rejected_rows.csv` with a `reject_reason` column.

## Region mapping

| region | cities |
|---|---|
| South | Bengaluru, Hyderabad, Chennai |
| West | Mumbai, Pune |
| North | Delhi |
| East | Kolkata |
