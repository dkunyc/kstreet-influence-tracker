{{ config(materialized='table') }}

-- Join extracted bill references from filings to Congress.gov bill metadata
-- and attach client intensity for context

with refs as (
    select * from {{ ref('int_filing_bill_refs') }}
),

bills as (
    select * from {{ ref('stg_bills') }}
),

intensity as (
    select
        client_name,
        filing_year,
        sum(total_spend) as year_spend,
        sum(filing_count) as year_filings
    from {{ ref('int_lobbying_intensity') }}
    group by 1, 2
)

select
    r.filing_uuid,
    r.filing_year,
    r.client_name,
    r.issue_code,
    r.bill_ref_normalized,
    r.description,
    b.congress,
    b.bill_type,
    b.bill_number,
    b.title as bill_title,
    b.origin_chamber,
    b.latest_action_date,
    b.latest_action_text,
    b.url as bill_url,
    i.year_spend,
    i.year_filings,
    case when b.bill_key is not null then true else false end as matched_to_congress
from refs r
left join bills b
    on r.bill_ref_normalized = b.bill_key
left join intensity i
    on r.client_name = i.client_name
   and r.filing_year = i.filing_year
