{# Lowercase, punctuation to spaces, whitespace collapsed. Mirrors _words() in ingestion/recall_match.py. #}
{% macro text_key(col) %}
trim(regexp_replace(regexp_replace(lower(coalesce({{ col }}, '')), '[^a-z0-9 ]', ' ', 'g'), '\s+', ' ', 'g'))
{% endmacro %}

{# Firm key: text_key without legal suffixes (and a joining "and"), so 'Pfizer Inc.', 'PFIZER' and
   'Eli Lilly and Company' reduce to their names. Mirrors firm_key() in ingestion/recall_match.py. #}
{% macro firm_key(col) %}
trim(regexp_replace(
    regexp_replace({{ text_key(col) }}, '\b(?:and )?(?:inc|llc|ltd|limited|corp|corporation|co|company|lp|llp|plc|pharmacy)\b', ' ', 'g'),
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

{# Release profile from a dosage form (and, for shortages, the drug name): extended and delayed release or
   liposomal products are different products from immediate release, so they get separate families. #}
{% macro release_type(col) %}
case
    when regexp_matches(upper({{ col }}), 'EXTENDED[ -]RELEASE|SUSTAINED|CONTROLLED[ -]RELEASE') then 'extended'
    when regexp_matches(upper({{ col }}), 'DELAYED[ -]RELEASE') then 'delayed'
    when regexp_matches(upper({{ col }}), 'LIPOSOMAL') then 'liposomal'
    else 'immediate'
end
{% endmacro %}
