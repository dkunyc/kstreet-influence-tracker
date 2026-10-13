{{ config(materialized='view') }}

select
    congress,
    bill_type,
    bill_number,
    title,
    origin_chamber,
    latest_action_date,
    latest_action_text,
    update_date,
    url,
    -- Build a normalized key that matches the extraction in int_filing_bill_refs
    -- e.g. "HR 1234", "S 567"
    upper(bill_type) || ' ' || bill_number as bill_key
from {{ source('raw', 'raw_bills') }}
where bill_type is not null
  and bill_number is not null
