{{ config(materialized='view') }}

-- District-level House election outcomes from MEDSL constituency returns.
-- Computes two-party vote share and margin for general elections.

with source as (
    select * from {{ source('raw', 'raw_medsl_house') }}
),

cleaned as (
    select
        year,
        upper(trim(state_po)) as state_po,
        try_cast(district as integer) as district,
        candidate,
        upper(trim(party)) as party,
        try_cast(candidatevotes as integer) as candidate_votes,
        try_cast(totalvotes as integer) as total_votes,
        coalesce(special, false) as special,
        lower(coalesce(stage, 'gen')) as stage
    from source
    where year is not null
      and state_po is not null
      and district is not null
),

general as (
    select *
    from cleaned
    where stage = 'gen'
      and special = false
      and candidate_votes is not null
      and total_votes > 0
),

-- Two-party share (Dem vs Rep when both present)
two_party as (
    select
        year,
        state_po,
        district,
        sum(case when party in ('DEMOCRAT', 'DEMOCRATIC', 'D') then candidate_votes else 0 end) as dem_votes,
        sum(case when party in ('REPUBLICAN', 'R') then candidate_votes else 0 end) as rep_votes,
        sum(candidate_votes) as total_candidate_votes,
        max(total_votes) as total_votes
    from general
    group by 1, 2, 3
)

select
    year,
    state_po,
    district,
    dem_votes,
    rep_votes,
    total_votes,
    case
        when (dem_votes + rep_votes) > 0
        then dem_votes * 1.0 / (dem_votes + rep_votes)
        else null
    end as dem_two_party_share,
    case
        when (dem_votes + rep_votes) > 0
        then abs(dem_votes - rep_votes) * 1.0 / (dem_votes + rep_votes)
        else null
    end as two_party_margin,
    case
        when dem_votes > rep_votes then 'D'
        when rep_votes > dem_votes then 'R'
        else 'TIE'
    end as winner_party
from two_party
where (dem_votes + rep_votes) > 0
