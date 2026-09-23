-- Star schema for the sales warehouse
-- written for SQLite (default), works on PostgreSQL with minor type changes

DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS customer_rfm;

CREATE TABLE dim_customer (
    customer_key   INTEGER PRIMARY KEY,
    customer_id    VARCHAR(20) NOT NULL UNIQUE,
    customer_name  VARCHAR(100),
    email          VARCHAR(150),
    city           VARCHAR(50),
    region         VARCHAR(20),
    segment        VARCHAR(20),
    signup_date    DATE
);

CREATE TABLE dim_product (
    product_key    INTEGER PRIMARY KEY,
    product_id     VARCHAR(20) NOT NULL UNIQUE,
    product_name   VARCHAR(100),
    category       VARCHAR(50),
    list_price     NUMERIC(12, 2)
);

CREATE TABLE dim_date (
    date_key       INTEGER PRIMARY KEY,   -- yyyymmdd
    full_date      DATE NOT NULL,
    day            INTEGER,
    month          INTEGER,
    month_name     VARCHAR(10),
    quarter        INTEGER,
    year           INTEGER,
    weekday        VARCHAR(10),
    is_weekend     INTEGER
);

CREATE TABLE fact_sales (
    sales_id       INTEGER PRIMARY KEY,
    order_id       VARCHAR(20) NOT NULL,
    date_key       INTEGER NOT NULL REFERENCES dim_date(date_key),
    customer_key   INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    product_key    INTEGER NOT NULL REFERENCES dim_product(product_key),
    channel        VARCHAR(20),
    quantity       INTEGER NOT NULL,
    unit_price     NUMERIC(12, 2) NOT NULL,
    discount_pct   NUMERIC(5, 2) DEFAULT 0,
    line_amount    NUMERIC(14, 2) NOT NULL,
    is_return      INTEGER DEFAULT 0
);

CREATE INDEX idx_fact_date ON fact_sales(date_key);
CREATE INDEX idx_fact_customer ON fact_sales(customer_key);
CREATE INDEX idx_fact_product ON fact_sales(product_key);

-- filled by the RFM step
CREATE TABLE customer_rfm (
    customer_id    VARCHAR(20) PRIMARY KEY,
    recency_days   INTEGER,
    frequency      INTEGER,
    monetary       NUMERIC(14, 2),
    r_score        INTEGER,
    f_score        INTEGER,
    m_score        INTEGER,
    rfm_score      VARCHAR(3),
    segment        VARCHAR(30)
);
