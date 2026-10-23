-- Every watchlist row has at least one reason and a positive score, and none is in shortage or has no marketed product.
select w.family_key, 'no reason' as problem from {{ ref('mart_watchlist') }} w
where w.reasons is null or len(w.reasons) = 0 or w.score <= 0
union all
select w.family_key, 'in active shortage' from {{ ref('mart_watchlist') }} w
join {{ ref('fct_family_risk_signals') }} s on s.family_key = w.family_key and s.role = 'current'
where s.in_active_shortage
union all
select family_key, 'no marketed products' from {{ ref('mart_watchlist') }} where n_suppliers < 1
