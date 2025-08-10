#!/usr/bin/env python3
"""
Fix for buyers report showing 0 clicks and registrations
Problem: When filtering by traffic source, click data is not being retrieved properly
"""

# The issue is in src/integrations/keitaro/client.py around line 580
# The second API call to get click data is likely failing or being filtered incorrectly

# Current problematic code:
"""
# Build report for clicks
report_params = {
    'metrics': ['clicks', 'unique_visitors', 'cost'],
    'filters': []
}

# Add time range
report_params['range'] = {
    'from': start_date,
    'to': end_date,
    'timezone': 'Europe/Moscow'
}

# Add traffic source filter if specified
if traffic_source_ids:
    report_params['filters'].append({
        'name': 'ts_id',
        'operator': 'IN_LIST',
        'expression': traffic_source_ids
    })

# Add buyer filter to only get data for buyers we found
if buyer_stats:
    report_params['filters'].append({
        'name': 'sub_id_1',
        'operator': 'IN_LIST', 
        'expression': list(buyer_stats.keys())
    })
"""

# The fix needs to:
# 1. Add 'group' parameter to group by buyer (sub_id_1)
# 2. Add correct columns to the request
# 3. Handle the response correctly

# Fixed version should be:
FIX = """
# Build report for clicks
report_params = {
    'columns': ['clicks', 'unique_clicks', 'cost'],  # Add columns
    'metrics': ['clicks', 'unique_clicks', 'cost'],
    'grouping': ['sub_id_1'],  # Group by buyer
    'filters': []
}

# Add time range  
report_params['range'] = {
    'from': start_date,
    'to': end_date,
    'timezone': 'Europe/Moscow'
}

# Add traffic source filter if specified
if traffic_source_ids:
    report_params['filters'].append({
        'name': 'ts_id',
        'operator': 'IN_LIST',
        'expression': traffic_source_ids
    })

# Try to get click data
try:
    click_data = await self._make_request('/admin_api/v1/report/build', method='POST', json=report_params)
    
    if click_data and 'rows' in click_data:
        for row in click_data['rows']:
            buyer = row.get('sub_id_1', 'unknown')  # Changed from 'buyer'
            if buyer in buyer_stats:
                buyer_stats[buyer]['clicks'] = row.get('clicks', 0)
                buyer_stats[buyer]['unique_visitors'] = row.get('unique_clicks', 0)  # Changed
                buyer_stats[buyer]['cost'] = float(row.get('cost', 0))
except Exception as e:
    logger.warning(f"Could not get click data (continuing with conversion data only): {e}")
"""

print("Fix needed in src/integrations/keitaro/client.py")
print("The issue is that the report/build API call needs proper grouping and column specification")
print("\nAlternative approach: Get ALL buyer stats without traffic source filter,")
print("then filter conversions by traffic source in the conversions/log call")