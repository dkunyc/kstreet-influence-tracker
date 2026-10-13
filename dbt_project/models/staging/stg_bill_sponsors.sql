{{ config(materialized='view') }}

select
    congress,
    bill_type,
    bill_number,
    bioguide_id,
    full_name,
    party,
    upper(trim(state)) as state_po,
    try_cast(district as integer) as district,
    -- House members have a district; Senate is statewide (district 0 or null)
    case
        when bill_type in ('HR', 'HRES', 'HJRES', 'HCONRES') then 'House'
        when bill_type in ('S', 'SRES', 'SJRES', 'SCONRES') then 'Senate'
        else null
    end as chamber
from {{ source('raw', 'raw_bill_sponsors') }}
where bioguide_id is not null
