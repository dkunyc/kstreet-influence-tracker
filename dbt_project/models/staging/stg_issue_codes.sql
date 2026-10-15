{{ config(materialized='table') }}

select
    code as issue_code,
    description as issue_description
from {{ ref('issue_codes') }}