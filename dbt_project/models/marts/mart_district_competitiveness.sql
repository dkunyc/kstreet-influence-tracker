{{ config(materialized='table') }}

-- District competitiveness snapshot for recent cycles.
-- Useful as a join target once bill sponsors are linked to districts.

select
    year,
    state_po,
    district,
    dem_two_party_share,
    two_party_margin,
    winner_party,
    total_votes,
    case
        when two_party_margin < 0.05 then 'toss_up'
        when two_party_margin < 0.10 then 'lean'
        else 'safe'
    end as competitiveness
from {{ ref('stg_house_districts') }}
where year >= 2018
order by year desc, state_po, district
