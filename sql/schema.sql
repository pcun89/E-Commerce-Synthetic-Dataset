-- Schema for the synthetic e-commerce dataset.
-- Works as-is in SQLite and PostgreSQL (MySQL: swap BOOLEAN for TINYINT(1)).
CREATE TABLE customers (
    customer_id         INT     PRIMARY KEY,
    first_name          TEXT    NOT NULL,
    last_name           TEXT    NOT NULL,
    email               TEXT   ,
    age                 INT    ,
    gender              TEXT   ,
    signup_date         DATE    NOT NULL,
    loyalty_tier        TEXT    NOT NULL, -- Bronze | Silver | Gold | Platinum
    city                TEXT    NOT NULL,
    state               TEXT    NOT NULL,
    country             TEXT    NOT NULL,
    acquisition_channel TEXT   ,
    marketing_opt_in    BOOLEAN
);
CREATE TABLE orders (
    order_id         INT             PRIMARY KEY,
    customer_id      INT             NOT NULL FOREIGN KEY REFERENCES customers (customer_id),
    order_date       DATE            NOT NULL,
    order_timestamp  TIMESTAMP       NOT NULL,
    product_category TEXT            NOT NULL,
    product_name     TEXT            NOT NULL,
    quantity         INT             NOT NULL,
    unit_price       NUMERIC (10, 2) NOT NULL,
    discount_percent INT             NOT NULL,
    subtotal         NUMERIC (10, 2) NOT NULL, -- quantity * unit_price * (1 - discount/100)
    shipping_cost    NUMERIC (10, 2) NOT NULL,
    tax_amount       NUMERIC (10, 2) NOT NULL, -- subtotal * state tax rate
    total_amount     NUMERIC (10, 2) NOT NULL, -- subtotal + shipping_cost + tax_amount
    payment_method   TEXT           ,
    order_status     TEXT            NOT NULL, -- Delivered | Shipped | Processing | Returned | Cancelled
    shipping_method  TEXT            NOT NULL,
    ship_date        DATE           ,
    delivery_date    DATE           ,
    sales_channel    TEXT           ,
    coupon_code      TEXT           ,
    is_gift          BOOLEAN        
);
CREATE INDEX idx_orders_customer
    ON orders(customer_id);

CREATE INDEX idx_orders_date
    ON orders(order_date);