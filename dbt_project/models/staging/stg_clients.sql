{{ config(materialized='view') }}

-- Client dimension with optional LobbyView entity resolution.
-- When raw_lobbyview_clients is present, use lob_id / client_uuid.
-- Otherwise fall back to normalized name.

with filings as (
    select distinct
        upper(trim(client_name)) as client_name_norm,
        client_name as client_name_raw
    from {{ ref('stg_filings') }}
    where client_name is not null
),

lobbyview as (
    select
        md5(upper(trim(client_name))) as lob_id,
        upper(trim(client_name)) as client_name_norm
    from {{ source('raw', 'raw_lobbyview_clients') }}
),

resolved as (
    select
        f.client_name_norm,
        f.client_name_raw,
        coalesce(lv.lob_id, md5(f.client_name_norm)) as client_id,
        case when lv.lob_id is not null then 'lobbyview' else 'name_hash' end as id_source
    from filings f
    left join lobbyview lv
        on f.client_name_norm = lv.client_name_norm
)

select
    client_id,
    client_name_norm as client_name,
    client_name_raw,
    id_source,
    count(*) over (partition by client_id) as filing_count
from resolved
