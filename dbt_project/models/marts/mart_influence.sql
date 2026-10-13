{{ config(materialized='table') }}

-- Client-level intensity with entity resolution source flag
select
    c.client_id,
    c.client_name,
    c.id_source,
    i.filing_year,
    i.filing_period,
    i.filing_count,
    i.total_spend,
    i.avg_spend_per_filing
from {{ ref('stg_clients') }} c
left join {{ ref('int_lobbying_intensity') }} i
    on c.client_name = i.client_name
