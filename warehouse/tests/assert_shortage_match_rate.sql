-- Shortage records linked to a product family must stay at or above 90%.
select match_rate
from (select value as match_rate from {{ ref('mart_data_quality') }} where metric = 'match_rate_to_family')
where match_rate < 0.90
