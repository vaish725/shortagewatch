{# Mirrors ingestion/utils/ndc.py. Parity is enforced by tests/assert_recall_match_parity.sql. #}

{# Hyphenated NDC -> 11 digit 5-4-2 (9 digit 5-4 for a product NDC); NULL if it does not parse. #}
{% macro normalize_ndc(col) %}
case
    when regexp_matches({{ col }}, '^[0-9]{1,5}-[0-9]{1,4}(-[0-9]{1,2})?$')
    then lpad(split_part({{ col }}, '-', 1), 5, '0')
         || lpad(split_part({{ col }}, '-', 2), 4, '0')
         || case when split_part({{ col }}, '-', 3) = '' then ''
                 else lpad(split_part({{ col }}, '-', 3), 2, '0') end
end
{% endmacro %}

{# NDC-shaped tokens in free text, as a list of hyphenated strings. RE2 has no lookbehind, so every
   delimiter is doubled first: a single delimiter can then close one token and open the next. #}
{% macro ndc_tokens(text) %}
regexp_extract_all(
    regexp_replace({{ text }}, '([^0-9-])', '\1\1', 'g'),
    '(?:^|[^0-9-])([0-9]{4,5}-[0-9]{3,4}(?:-[0-9]{1,2})?)(?:$|[^0-9-])', 1)
{% endmacro %}

{# Tokens that directly follow the word NDC (up to 12 non-digit characters, not ending in a hyphen). #}
{% macro ndc_keyword_tokens(text) %}
regexp_extract_all({{ text }},
    '(?i)NDC(?:[^0-9]{0,11}[^0-9-])?([0-9]{4,5}-[0-9]{3,4}(?:-[0-9]{1,2})?)(?:$|[^0-9-])', 1)
{% endmacro %}
