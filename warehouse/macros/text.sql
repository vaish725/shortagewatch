{# Lowercase, punctuation to spaces, whitespace collapsed. Mirrors _words() in ingestion/recall_match.py. #}
{% macro text_key(col) %}
trim(regexp_replace(regexp_replace(lower(coalesce({{ col }}, '')), '[^a-z0-9 ]', ' ', 'g'), '\s+', ' ', 'g'))
{% endmacro %}

{# Firm key: text_key without legal suffixes, so 'Pfizer Inc.' and 'PFIZER' agree. Mirrors firm_key(). #}
{% macro firm_key(col) %}
trim(regexp_replace(
    regexp_replace({{ text_key(col) }}, '\b(inc|llc|ltd|limited|corp|corporation|co|company|lp|llp|plc|pharmacy)\b', ' ', 'g'),
    '\s+', ' ', 'g'))
{% endmacro %}

{# Parses an openFDA MM/DD/YYYY or YYYYMMDD string; NULL when blank or malformed. #}
{% macro parse_date(col) %}
coalesce(try_strptime({{ col }}, '%m/%d/%Y'), try_strptime({{ col }}, '%Y%m%d'))::date
{% endmacro %}

{# JSON array string -> VARCHAR[] (empty list when missing). #}
{% macro json_list(col, path) %}
coalesce(from_json(json_extract({{ col }}, '{{ path }}'), '["VARCHAR"]'), []::varchar[])
{% endmacro %}
