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