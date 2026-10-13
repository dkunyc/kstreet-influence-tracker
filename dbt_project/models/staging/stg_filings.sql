{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'raw_filings') }}
),

cleaned as (
    select
        filing_uuid,
        filing_type,
        filing_year,
        filing_period,
        coalesce(income, 0) as income,
        coalesce(expenses, 0) as expenses,
        coalesce(income, 0) + coalesce(expenses, 0) as total_spend,
        try_cast(dt_posted as timestamp) as posted_at,
        upper(trim(registrant_name)) as registrant_name,
        upper(trim(client_name)) as client_name,
        raw_json
    from source
    where filing_uuid is not null
)

select * from cleaned
