{# Number of files matching a glob (0 when none). Lets optional sources degrade to a warning instead of an error. #}
{% macro glob_count(pattern) %}
{% if execute %}
    {% set r = run_query("select count(*) from glob('" ~ pattern ~ "')") %}
    {{ return(r.columns[0].values()[0]) }}
{% else %}
    {{ return(1) }}
{% endif %}
{% endmacro %}
