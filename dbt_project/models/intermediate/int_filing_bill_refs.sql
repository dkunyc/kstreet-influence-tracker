{{ config(materialized='view') }}

-- Extract bill references from the free-text lobbying activity descriptions
-- stored in the raw JSON of LDA filings.
-- Matches patterns like: H.R. 1234, HR 1234, S. 567, S 567, H.J.Res. 1, etc.

with filings as (
    select
        filing_uuid,
        filing_year,
        client_name,
        raw_json
    from {{ ref('stg_filings') }}
    where raw_json is not null
),

-- Unnest lobbying activities and pull the description text
activities as (
    select
        f.filing_uuid,
        f.filing_year,
        f.client_name,
        unnest(from_json(json_extract(f.raw_json, '$.lobbying_activities'), '["JSON"]')) as activity
    from filings f
    where json_extract(f.raw_json, '$.lobbying_activities') is not null
),

descriptions as (
    select
        filing_uuid,
        filing_year,
        client_name,
        activity ->> 'description' as description,
        activity ->> 'general_issue_code' as issue_code
    from activities
    where activity ->> 'description' is not null
),

-- Regex extract of bill numbers
bill_refs as (
    select
        filing_uuid,
        filing_year,
        client_name,
        issue_code,
        description,
        -- Normalize common formats to a consistent key
        regexp_extract_all(
            upper(description),
            '(H\.?R\.?|S\.?|H\.?J\.?RES\.?|S\.?J\.?RES\.?|H\.?CON\.?RES\.?|S\.?CON\.?RES\.?|H\.?RES\.?|S\.?RES\.?)\s*(\d+)',
            0
        ) as raw_matches
    from descriptions
),

exploded as (
    select
        filing_uuid,
        filing_year,
        client_name,
        issue_code,
        description,
        unnest(raw_matches) as raw_bill_ref
    from bill_refs
    where array_length(raw_matches) > 0
),

normalized as (
    select
        filing_uuid,
        filing_year,
        client_name,
        issue_code,
        description,
        -- Clean to a joinable key: e.g. "HR 1234", "S 567"
        regexp_replace(
            regexp_replace(raw_bill_ref, '\.', '', 'g'),
            '\s+', ' ', 'g'
        ) as bill_ref_normalized
    from exploded
)

select distinct
    filing_uuid,
    filing_year,
    client_name,
    issue_code,
    bill_ref_normalized,
    description
from normalized
where bill_ref_normalized is not null
  and bill_ref_normalized != ''
