{{ config(materialized='table') }}

-- Filing → bill → sponsor → district election outcome
-- House only for district join; Senate stays statewide

with filing_bills as (
    select * from {{ ref('mart_filing_bills') }}
    where matched_to_congress = true
),

sponsors as (
    select * from {{ ref('stg_bill_sponsors') }}
),

districts as (
    select * from {{ ref('mart_district_competitiveness') }}
),

-- Pre-compute the nearest prior election year per sponsor + filing year
nearest_election as (
    select
        s.bioguide_id,
        s.congress,
        s.bill_type,
        s.bill_number,
        fb.filing_year,
        max(d.year) as election_year
    from filing_bills fb
    inner join sponsors s
        on fb.congress = s.congress
       and fb.bill_type = s.bill_type
       and fb.bill_number = s.bill_number
    left join districts d
        on s.chamber = 'House'
       and s.state_po = d.state_po
       and s.district = d.district
       and d.year <= fb.filing_year
    group by 1, 2, 3, 4, 5
)

select
    fb.filing_uuid,
    fb.filing_year,
    fb.client_name,
    fb.bill_ref_normalized,
    fb.bill_title,
    fb.year_spend,
    s.bioguide_id,
    s.full_name as sponsor_name,
    s.party as sponsor_party,
    s.state_po,
    s.district,
    s.chamber,
    d.year as election_year,
    d.dem_two_party_share,
    d.two_party_margin,
    d.winner_party,
    d.competitiveness
from filing_bills fb
inner join sponsors s
    on fb.congress = s.congress
   and fb.bill_type = s.bill_type
   and fb.bill_number = s.bill_number
left join nearest_election ne
    on s.bioguide_id = ne.bioguide_id
   and s.congress = ne.congress
   and s.bill_type = ne.bill_type
   and s.bill_number = ne.bill_number
   and fb.filing_year = ne.filing_year
left join districts d
    on s.state_po = d.state_po
   and s.district = d.district
   and d.year = ne.election_year