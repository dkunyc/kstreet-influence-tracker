{{ config(materialized='table') }}

with filings as (
    select * from {{ ref('stg_filings') }}
),

intensity as (
    select
        client_name,
        filing_year,
        filing_period,
        count(*) as filing_count,
        sum(total_spend) as total_spend,
        avg(total_spend) as avg_spend_per_filing
    from filings
    group by 1, 2, 3
)

select * from intensity
