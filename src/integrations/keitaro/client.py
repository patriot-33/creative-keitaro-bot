"""
Keitaro API Client for interacting with Keitaro tracker
"""
import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from core.enums import ReportPeriod
from core.config import settings

logger = logging.getLogger(__name__)


class KeitaroClient:
    """Async client for Keitaro API"""
    
    def __init__(self):
        self.base_url = settings.keitaro_base_url.rstrip('/')
        self.api_key = settings.keitaro_api_token
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            
    async def _make_request(
        self, 
        endpoint: str, 
        method: str = 'GET',
        params: Optional[Dict] = None,
        json: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Keitaro API"""
        if not self.session:
            raise RuntimeError("Client not initialized. Use 'async with KeitaroClient()' pattern")
            
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            'Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        try:
            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    response_text = await response.text()
                    logger.error(f"API request failed: {response.status} - {response_text}")
                    
                    # Check for specific error about traffic_source_id
                    if "traffic_source_id" in response_text.lower():
                        logger.error("CRITICAL: API error mentions 'traffic_source_id' - this should be 'ts_id'!")
                        logger.error(f"Request payload: {json}")
                    
                    return {}
                    
        except Exception as e:
            logger.error(f"Request error for {endpoint}: {e}")
            if json and "traffic_source_id" in str(json):
                logger.error("CRITICAL: Request payload contains 'traffic_source_id' - should use 'ts_id'!")
                logger.error(f"Request payload: {json}")
            return {}
    
    async def get_traffic_sources(self) -> List[Dict[str, Any]]:
        """Get all traffic sources"""
        try:
            data = await self._make_request('/admin_api/v1/traffic_sources')
            return data if isinstance(data, list) else data.get('traffic_sources', [])
        except Exception as e:
            logger.error(f"Failed to get traffic sources: {e}")
            return []
    
    async def get_stats_by_buyers(
        self,
        period: ReportPeriod = ReportPeriod.YESTERDAY,
        buyer_id: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get statistics by buyers for a given period"""
        
        # Determine time range
        if period == ReportPeriod.CUSTOM and custom_start and custom_end:
            start_date = custom_start
            end_date = custom_end
        else:
            # For standard periods
            if period in [ReportPeriod.TODAY, ReportPeriod.YESTERDAY]:
                from datetime import datetime, timedelta
                
                if period == ReportPeriod.TODAY:
                    date = datetime.now()
                else:
                    date = datetime.now() - timedelta(days=1)
                
                # Use Moscow timezone boundaries
                start_date = date.strftime('%Y-%m-%d 00:00:00')
                end_date = date.strftime('%Y-%m-%d 23:59:59')
            else:
                # For other periods, calculate dates
                from datetime import datetime, timedelta
                now = datetime.now()
                
                if period == ReportPeriod.LAST_24H:
                    start_date = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
                    end_date = now.strftime('%Y-%m-%d %H:%M:%S')
                elif period == ReportPeriod.LAST_3D:
                    start_date = (now - timedelta(days=3)).strftime('%Y-%m-%d 00:00:00')
                    end_date = now.strftime('%Y-%m-%d 23:59:59')
                elif period == ReportPeriod.LAST_7D:
                    start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d 00:00:00')
                    end_date = now.strftime('%Y-%m-%d 23:59:59')
                elif period == ReportPeriod.LAST_30D:
                    start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
                    end_date = now.strftime('%Y-%m-%d 23:59:59')
                else:
                    start_date = (now - timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')
                    end_date = (now - timedelta(days=1)).strftime('%Y-%m-%d 23:59:59')
        
        # Build report request
        report_params = {
            'metrics': ['clicks', 'unique_visitors', 'conversions', 'cost'],
            'filters': [],
            'range': {
                'from': start_date,
                'to': end_date,
                'timezone': 'Europe/Moscow'
            }
        }
        
        # Add buyer filter if specified
        if buyer_id:
            report_params['filters'].append({
                'name': 'sub_id_1',
                'operator': 'EQUALS',
                'expression': buyer_id
            })
        
        try:
            # Get basic stats
            data = await self._make_request('/admin_api/v1/report/build', method='POST', json=report_params)
            
            if not data or 'rows' not in data:
                return []
            
            # Get detailed conversion data using the existing method logic
            conversion_data = await self._get_conversion_stats(start_date, end_date, buyer_id)
            
            # Combine the data
            result = []
            for row in data['rows']:
                buyer = row.get('buyer', 'unknown')
                if buyer == 'unknown':
                    continue
                    
                buyer_data = {
                    'buyer_id': buyer,
                    'clicks': row.get('clicks', 0),
                    'unique_visitors': row.get('unique_visitors', 0),
                    'conversions': row.get('conversions', 0),
                    'leads': 0,
                    'sales': 0,
                    'revenue': 0.0,
                    'cost': float(row.get('cost', 0)),
                    'countries': [],
                    'offers': [],
                    'streams': []
                }
                
                # Add conversion data if available
                if buyer in conversion_data:
                    conv_data = conversion_data[buyer]
                    buyer_data.update({
                        'leads': conv_data.get('leads', 0),
                        'sales': conv_data.get('sales', 0),
                        'revenue': conv_data.get('revenue', 0.0),
                        'countries': conv_data.get('countries', []),
                        'offers': conv_data.get('offers', []),
                        'streams': conv_data.get('streams', [])
                    })
                
                # Calculate rates and profit
                buyer_data['profit'] = buyer_data['revenue'] - buyer_data['cost']
                buyer_data['reg_cr'] = (buyer_data['leads'] / buyer_data['clicks'] * 100) if buyer_data['clicks'] > 0 else 0
                buyer_data['dep_rate'] = (buyer_data['sales'] / buyer_data['leads'] * 100) if buyer_data['leads'] > 0 else 0
                
                result.append(buyer_data)
            
            # Sort by revenue
            result.sort(key=lambda x: x['revenue'], reverse=True)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get buyer stats: {e}")
            return []
    
    async def _get_conversion_stats(
        self, 
        start_date: str, 
        end_date: str, 
        buyer_id: Optional[str] = None
    ) -> Dict[str, Dict]:
        """Get detailed conversion statistics"""
        params = {
            'start_at': start_date,
            'end_at': end_date,
            'timezone': 'Europe/Moscow'
        }
        
        try:
            data = await self._make_request('/admin_api/v1/conversions/log', params=params)
            
            if not data:
                return {}
            
            # Handle both list and dict responses
            rows = data if isinstance(data, list) else data.get('rows', [])
            
            # Process conversions by buyer
            buyer_stats = {}
            
            for row in rows:
                buyer = row.get('sub_id_1', 'unknown')
                if not buyer or buyer == 'unknown':
                    continue
                    
                # Filter by buyer if specified
                if buyer_id and buyer != buyer_id:
                    continue
                
                # Initialize buyer if not exists
                if buyer not in buyer_stats:
                    buyer_stats[buyer] = {
                        'leads': 0,
                        'sales': 0,
                        'revenue': 0.0,
                        'countries': set(),
                        'offers': set(),
                        'streams': set()
                    }
                
                # Update stats based on conversion status
                status = row.get('status', '')
                
                if status == 'lead':
                    buyer_stats[buyer]['leads'] += 1
                elif status == 'sale':
                    buyer_stats[buyer]['sales'] += 1
                    buyer_stats[buyer]['revenue'] += float(row.get('revenue', 0))
                
                # Add metadata
                if row.get('country'):
                    buyer_stats[buyer]['countries'].add(row['country'])
                if row.get('offer'):
                    buyer_stats[buyer]['offers'].add(row['offer'])
                if row.get('stream'):
                    buyer_stats[buyer]['streams'].add(row['stream'])
            
            # Convert sets to lists
            for buyer_data in buyer_stats.values():
                buyer_data['countries'] = list(buyer_data['countries'])
                buyer_data['offers'] = list(buyer_data['offers'])
                buyer_data['streams'] = list(buyer_data['streams'])
            
            return buyer_stats
            
        except Exception as e:
            logger.error(f"Failed to get conversion stats: {e}")
            return {}
    
    async def get_deposits_by_sale_datetime(
        self,
        period: ReportPeriod = ReportPeriod.YESTERDAY,
        buyer_id: Optional[str] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Get deposits data filtered by sale_datetime"""
        
        # Determine time range (same logic as other methods)
        if period == ReportPeriod.CUSTOM and custom_start and custom_end:
            start_date = custom_start
            end_date = custom_end
        else:
            # Calculate dates based on period
            from datetime import datetime, timedelta
            now = datetime.now()
            
            if period == ReportPeriod.TODAY:
                date = now
                start_date = date.strftime('%Y-%m-%d 00:00:00')
                end_date = date.strftime('%Y-%m-%d 23:59:59')
            elif period == ReportPeriod.YESTERDAY:
                date = now - timedelta(days=1)
                start_date = date.strftime('%Y-%m-%d 00:00:00')
                end_date = date.strftime('%Y-%m-%d 23:59:59')
            else:
                # Default to yesterday
                date = now - timedelta(days=1)
                start_date = date.strftime('%Y-%m-%d 00:00:00')
                end_date = date.strftime('%Y-%m-%d 23:59:59')
        
        params = {
            'start_at': start_date,
            'end_at': end_date,
            'timezone': 'Europe/Moscow'
        }
        
        try:
            data = await self._make_request('/admin_api/v1/conversions/log', params=params)
            
            if not data:
                return {}
            
            rows = data if isinstance(data, list) else data.get('rows', [])
            
            # Filter and process deposits
            deposits_data = {}
            
            for row in rows:
                buyer = row.get('sub_id_1', 'unknown')
                status = row.get('status', '')
                sale_datetime = row.get('sale_datetime', '')
                
                if (status == 'sale' and buyer and buyer != 'unknown' and 
                    sale_datetime and start_date <= sale_datetime <= end_date):
                    
                    # Filter by buyer if specified
                    if buyer_id and buyer != buyer_id:
                        continue
                    
                    if buyer not in deposits_data:
                        deposits_data[buyer] = {
                            'deposits': 0,
                            'revenue': 0.0,
                            'conversions': []
                        }
                    
                    deposits_data[buyer]['deposits'] += 1
                    deposits_data[buyer]['revenue'] += float(row.get('revenue', 0))
                    deposits_data[buyer]['conversions'].append({
                        'sub_id': row.get('sub_id', ''),
                        'revenue': float(row.get('revenue', 0)),
                        'sale_datetime': sale_datetime,
                        'offer': row.get('offer', ''),
                        'country': row.get('country', '')
                    })
            
            return deposits_data
            
        except Exception as e:
            logger.error(f"Failed to get deposits by sale datetime: {e}")
            return {}

    async def get_buyers_by_traffic_source(
        self,
        period: ReportPeriod = ReportPeriod.LAST_24H,
        traffic_source_ids: Optional[List[str]] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get buyers statistics using conversions data filtered by traffic sources
        
        This method uses the conversions/log endpoint to get accurate data
        filtered by traffic sources.
        """
        
        # Determine time range
        if period == ReportPeriod.CUSTOM and custom_start and custom_end:
            start_date = custom_start
            end_date = custom_end
        else:
            # For standard periods
            if period in [ReportPeriod.TODAY, ReportPeriod.YESTERDAY]:
                from datetime import datetime, timedelta
                
                if period == ReportPeriod.TODAY:
                    date = datetime.now()
                else:
                    date = datetime.now() - timedelta(days=1)
                
                # Use full calendar days for accurate reporting
                # Convert Moscow time boundaries to UTC for API (Moscow is UTC+3)
                if period == ReportPeriod.YESTERDAY:
                    yesterday = datetime.now() - timedelta(days=1)
                    # Moscow day boundaries (00:00-23:59) converted to UTC (21:00-20:59)
                    moscow_start = yesterday.strftime('%Y-%m-%d 00:00:00')
                    moscow_end = yesterday.strftime('%Y-%m-%d 23:59:59')
                    # Convert to UTC by subtracting 3 hours
                    moscow_start_dt = datetime.strptime(moscow_start, '%Y-%m-%d %H:%M:%S')
                    moscow_end_dt = datetime.strptime(moscow_end, '%Y-%m-%d %H:%M:%S')
                    utc_start_dt = moscow_start_dt - timedelta(hours=3)
                    utc_end_dt = moscow_end_dt - timedelta(hours=3)
                    start_date = utc_start_dt.strftime('%Y-%m-%d %H:%M:%S')
                    end_date = utc_end_dt.strftime('%Y-%m-%d %H:%M:%S')
                else:  # TODAY
                    today = datetime.now()
                    # Moscow day boundaries (00:00-23:59) converted to UTC (21:00-20:59)
                    moscow_start = today.strftime('%Y-%m-%d 00:00:00')
                    moscow_end = today.strftime('%Y-%m-%d 23:59:59')
                    # Convert to UTC by subtracting 3 hours
                    moscow_start_dt = datetime.strptime(moscow_start, '%Y-%m-%d %H:%M:%S')
                    moscow_end_dt = datetime.strptime(moscow_end, '%Y-%m-%d %H:%M:%S')
                    utc_start_dt = moscow_start_dt - timedelta(hours=3)
                    utc_end_dt = moscow_end_dt - timedelta(hours=3)
                    start_date = utc_start_dt.strftime('%Y-%m-%d %H:%M:%S')
                    end_date = utc_end_dt.strftime('%Y-%m-%d %H:%M:%S')
                
                logger.info(f"Using calendar day boundaries for conversions: {start_date} - {end_date} (UTC)")
            else:
                # For other periods, calculate dates
                from datetime import datetime, timedelta
                now = datetime.now()
                
                if period == ReportPeriod.LAST_24H:
                    start_date = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
                    end_date = now.strftime('%Y-%m-%d %H:%M:%S')
                elif period == ReportPeriod.LAST_3D:
                    start_date = (now - timedelta(days=3)).strftime('%Y-%m-%d 00:00:00')
                    end_date = now.strftime('%Y-%m-%d 23:59:59')
                elif period == ReportPeriod.LAST_7D:
                    start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d 00:00:00')
                    end_date = now.strftime('%Y-%m-%d 23:59:59')
                elif period == ReportPeriod.LAST_30D:
                    start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
                    end_date = now.strftime('%Y-%m-%d 23:59:59')
                else:
                    start_date = (now - timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')
                    end_date = (now - timedelta(days=1)).strftime('%Y-%m-%d 23:59:59')
        
        # Get conversions data using POST method with proper JSON payload
        payload = {
            "limit": 10000,  # Get more records
            "columns": [
                "conversion_id", "sub_id_1", "status", "revenue", 
                "ts_id", "ts", "country", 
                "offer", "stream", "click_datetime", "postback_datetime"
            ],
            "filters": [
                {
                    "name": "postback_datetime",  # Use postback_datetime for accurate CSV matching
                    "operator": "BETWEEN",
                    "expression": [start_date, end_date]
                }
                # Remove status filter to get both leads and sales
            ],
            "sort": [
                {"name": "postback_datetime", "order": "DESC"}
            ]
        }
        
        try:
            logger.info(f"Getting conversions for traffic source filtering: {start_date} - {end_date}")
            
            # Get all conversions using POST method
            data = await self._make_request('/admin_api/v1/conversions/log', method='POST', json=payload)
            
            if not data:
                return []
            
            # Handle both list and dict responses
            rows = data.get('rows', []) if isinstance(data, dict) else data if isinstance(data, list) else []
            
            # Get traffic sources if needed
            if traffic_source_ids:
                traffic_sources = await self.get_traffic_sources()
                source_name_map = {str(ts['id']): ts['name'] for ts in traffic_sources}
            
            # Process conversions by buyer
            buyer_stats = {}
            
            for row in rows:
                buyer = row.get('sub_id_1', 'unknown')
                if not buyer or buyer == 'unknown':
                    continue
                
                # Filter by traffic source if specified
                if traffic_source_ids:
                    # Get traffic source from the conversion
                    traffic_source = row.get('ts_id', row.get('ts', ''))
                    
                    # Check if it's in our filter list
                    if str(traffic_source) not in traffic_source_ids:
                        continue
                
                # Initialize buyer if not exists
                if buyer not in buyer_stats:
                    buyer_stats[buyer] = {
                        'buyer_id': buyer,
                        'clicks': 0,
                        'unique_visitors': 0,
                        'conversions': 0,
                        'leads': 0,
                        'sales': 0,
                        'revenue': 0.0,
                        'cost': 0.0,
                        'countries': set(),
                        'offers': set(),
                        'streams': set()
                    }
                
                # Update stats based on conversion status
                status = row.get('status', '')
                buyer_stats[buyer]['conversions'] += 1
                
                if status == 'lead':
                    buyer_stats[buyer]['leads'] += 1
                elif status == 'sale':
                    buyer_stats[buyer]['sales'] += 1
                    buyer_stats[buyer]['revenue'] += float(row.get('revenue', 0))
                
                # Add metadata
                if row.get('country'):
                    buyer_stats[buyer]['countries'].add(row['country'])
                if row.get('offer'):
                    buyer_stats[buyer]['offers'].add(row['offer'])
                if row.get('stream'):
                    buyer_stats[buyer]['streams'].add(row['stream'])
            
            # Now get click data for these buyers
            # Build report for clicks with proper grouping
            report_params = {
                'columns': ['sub_id_1', 'clicks', 'global_unique_clicks', 'conversions', 'leads', 'cost'],
                'metrics': ['clicks', 'global_unique_clicks', 'conversions', 'leads', 'cost'],
                'grouping': ['sub_id_1'],  # Group by buyer
                'filters': []
            }
            
            # Add time range (use same time range as conversions for consistency)
            report_params['range'] = {
                'from': start_date,
                'to': end_date,
                'timezone': 'Europe/Moscow'
            }
            
            # Add traffic source filter if specified
            if traffic_source_ids:
                report_params['filters'].append({
                    'name': 'ts_id',  # Correct field name is ts_id, NOT traffic_source_id
                    'operator': 'IN_LIST',
                    'expression': traffic_source_ids
                })
            
            # Don't filter by buyers - get all buyers for this traffic source
            # We'll match them later
            
            # Validate that we're not using traffic_source_id in filters
            for filter_item in report_params.get('filters', []):
                if filter_item.get('name') == 'traffic_source_id':
                    logger.error("CRITICAL: Found 'traffic_source_id' in filter - changing to 'ts_id'")
                    filter_item['name'] = 'ts_id'
            
            # Try to get click data (optional - if it fails, continue with conversion data only)
            try:
                click_data = await self._make_request('/admin_api/v1/report/build', method='POST', json=report_params)
                
                if click_data and 'rows' in click_data:
                    for row in click_data['rows']:
                        buyer = row.get('sub_id_1', 'unknown')
                        if buyer in buyer_stats:
                            buyer_stats[buyer]['clicks'] = row.get('clicks', 0)
                            buyer_stats[buyer]['unique_visitors'] = row.get('global_unique_clicks', 0)
                            buyer_stats[buyer]['cost'] = float(row.get('cost', 0))
                            # Don't overwrite leads - they're already counted from conversions/log API
            except Exception as e:
                logger.warning(f"Could not get click data (continuing with conversion data only): {e}")
                # Continue without click data - conversion data is more important
            
            # Convert sets to lists and calculate profit
            result = []
            for buyer_data in buyer_stats.values():
                buyer_data['countries'] = list(buyer_data['countries'])
                buyer_data['offers'] = list(buyer_data['offers'])
                buyer_data['streams'] = list(buyer_data['streams'])
                buyer_data['profit'] = buyer_data['revenue'] - buyer_data['cost']
                result.append(buyer_data)
            
            # Sort by revenue
            result.sort(key=lambda x: x['revenue'], reverse=True)
            
            logger.info(f"Found {len(result)} buyers with traffic source filter")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get buyers by traffic source: {e}")
            return []
    
    async def get_stats_by_traffic_sources(
        self,
        period: ReportPeriod = ReportPeriod.YESTERDAY,
        traffic_source_ids: Optional[List[str]] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get statistics by traffic sources"""
        try:
            # Determine date range
            if period == ReportPeriod.CUSTOM and custom_start and custom_end:
                start_date = custom_start
                end_date = custom_end
            else:
                if period in [ReportPeriod.TODAY, ReportPeriod.YESTERDAY]:
                    if period == ReportPeriod.TODAY:
                        date = datetime.now()
                    else:
                        date = datetime.now() - timedelta(days=1)
                    
                    # Use full calendar days for accurate reporting
                    start_date = date.strftime('%Y-%m-%d 00:00:00')
                    end_date = date.strftime('%Y-%m-%d 23:59:59')
                else:
                    # For other periods, calculate dates
                    now = datetime.now()
                    if period == ReportPeriod.LAST_24H:
                        start_date = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
                        end_date = now.strftime('%Y-%m-%d %H:%M:%S')
                    elif period == ReportPeriod.LAST_7D:
                        start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d 00:00:00')
                        end_date = now.strftime('%Y-%m-%d 23:59:59')
                    elif period == ReportPeriod.LAST_30D:
                        start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
                        end_date = now.strftime('%Y-%m-%d 23:59:59')
                    else:
                        # Default to yesterday
                        yesterday = now - timedelta(days=1)
                        start_date = yesterday.strftime('%Y-%m-%d 00:00:00')
                        end_date = yesterday.strftime('%Y-%m-%d 23:59:59')

            # Use provided traffic source filter
            traffic_source_filter = traffic_source_ids or []
            
            # Build report params for traffic sources
            report_params = {
                'metrics': ['clicks', 'global_unique_clicks', 'conversions', 'leads', 'sales', 'revenue', 'cost'],
                'filters': [
                    {
                        'name': 'datetime',
                        'operator': 'BETWEEN',
                        'expression': [start_date, end_date]
                    }
                ],
                'sort': [{'name': 'revenue', 'order': 'DESC'}],
                'limit': 1000
            }
            
            # Add traffic source filter if available
            if traffic_source_filter:
                report_params['filters'].append({
                    'name': 'ts_id',  # Correct field name is ts_id, NOT traffic_source_id
                    'operator': 'IN_LIST',
                    'expression': traffic_source_filter
                })

            logger.info(f"Getting traffic sources stats: {start_date} - {end_date}")
            logger.debug(f"Report params: {report_params}")
            
            # Validate that we're not using traffic_source_id in filters
            for filter_item in report_params.get('filters', []):
                if filter_item.get('name') == 'traffic_source_id':
                    logger.error("CRITICAL: Found 'traffic_source_id' in filter - changing to 'ts_id'")
                    filter_item['name'] = 'ts_id'
            
            # Try to get traffic sources data
            data = await self._make_request('/admin_api/v1/report/build', method='POST', json=report_params)
            
            if not data or 'rows' not in data:
                logger.warning("No traffic sources data received")
                return []

            # Process data and create per-traffic-source results
            if data['rows']:
                row = data['rows'][0]  # Single aggregated row from API
                
                # Get traffic sources for proper naming
                try:
                    sources = await self.get_traffic_sources()
                    source_map = {str(ts['id']): ts['name'] for ts in sources}
                except Exception as e:
                    logger.warning(f"Could not get traffic source names: {e}")
                    source_map = {}
                
                # Create result for each requested traffic source
                result = []
                
                if traffic_source_filter:
                    # Return data for each filtered traffic source
                    for ts_id in traffic_source_filter:
                        ts_name = source_map.get(ts_id, f"Traffic Source {ts_id}")
                        result.append({
                            'traffic_source_id': int(ts_id),
                            'traffic_source_name': ts_name,
                            'clicks': int(row.get('clicks', 0)),
                            'unique_clicks': int(row.get('global_unique_clicks', 0)),
                            'conversions': int(row.get('conversions', 0)),
                            'leads': int(row.get('leads', 0)),
                            'sales': int(row.get('sales', 0)),
                            'revenue': float(row.get('revenue', 0)),
                            'cost': float(row.get('cost', 0)),
                            'profit': float(row.get('revenue', 0)) - float(row.get('cost', 0))
                        })
                else:
                    # Return aggregated data for all traffic
                    result = [{
                        'traffic_source_id': 0,
                        'traffic_source_name': 'All Traffic',
                        'clicks': int(row.get('clicks', 0)),
                        'unique_clicks': int(row.get('global_unique_clicks', 0)),
                        'conversions': int(row.get('conversions', 0)),
                        'leads': int(row.get('leads', 0)),
                        'sales': int(row.get('sales', 0)),
                        'revenue': float(row.get('revenue', 0)),
                        'cost': float(row.get('cost', 0)),
                        'profit': float(row.get('revenue', 0)) - float(row.get('cost', 0))
                    }]
                
                logger.info(f"Found {len(result)} traffic source(s) with data")
                return result
            
            logger.warning("No aggregated traffic data found")
            return []
            
        except Exception as e:
            logger.error(f"Failed to get traffic sources stats: {e}")
            return []
    
    async def get_stats_by_creatives(
        self,
        period: ReportPeriod = ReportPeriod.YESTERDAY,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get statistics by creatives"""
        try:
            # Determine date range
            if period == ReportPeriod.CUSTOM and custom_start and custom_end:
                start_date = custom_start
                end_date = custom_end
            else:
                if period in [ReportPeriod.TODAY, ReportPeriod.YESTERDAY]:
                    if period == ReportPeriod.TODAY:
                        date = datetime.now()
                    else:
                        date = datetime.now() - timedelta(days=1)
                    
                    # Use full calendar days for accurate reporting
                    start_date = date.strftime('%Y-%m-%d 00:00:00')
                    end_date = date.strftime('%Y-%m-%d 23:59:59')
                else:
                    # For other periods, calculate dates
                    now = datetime.now()
                    if period == ReportPeriod.LAST_24H:
                        start_date = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
                        end_date = now.strftime('%Y-%m-%d %H:%M:%S')
                    elif period == ReportPeriod.LAST_7D:
                        start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d 00:00:00')
                        end_date = now.strftime('%Y-%m-%d 23:59:59')
                    elif period == ReportPeriod.LAST_30D:
                        start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
                        end_date = now.strftime('%Y-%m-%d 23:59:59')
                    else:
                        # Default to yesterday
                        yesterday = now - timedelta(days=1)
                        start_date = yesterday.strftime('%Y-%m-%d 00:00:00')
                        end_date = yesterday.strftime('%Y-%m-%d 23:59:59')

            # Build report params for creatives (using sub_id as creative identifier)
            report_params = {
                'columns': [
                    'sub_id', 'clicks', 'unique_clicks', 'conversions', 
                    'leads', 'sales', 'revenue', 'cost'
                ],
                'filters': [
                    {
                        'name': 'datetime',
                        'operator': 'BETWEEN',
                        'expression': [start_date, end_date]
                    }
                ],
                'metrics': ['clicks', 'unique_clicks', 'conversions', 'leads', 'sales', 'revenue', 'cost'],
                'sort': [{'name': 'revenue', 'order': 'DESC'}],
                'limit': 1000
            }

            logger.info(f"Getting creatives stats: {start_date} - {end_date}")
            
            # Try to get creatives data
            data = await self._make_request('/admin_api/v1/report/build', method='POST', json=report_params)
            
            if not data or 'rows' not in data:
                logger.warning("No creatives data received")
                return []

            # Process creatives data
            result = []
            for row in data['rows']:
                creative_data = {
                    'creative_id': row.get('sub_id', 'unknown'),
                    'clicks': int(row.get('clicks', 0)),
                    'unique_clicks': int(row.get('unique_clicks', 0)),
                    'conversions': int(row.get('conversions', 0)),
                    'leads': int(row.get('leads', 0)),
                    'sales': int(row.get('sales', 0)),
                    'revenue': float(row.get('revenue', 0)),
                    'cost': float(row.get('cost', 0)),
                    'profit': float(row.get('revenue', 0)) - float(row.get('cost', 0)),
                    'epc': float(row.get('revenue', 0)) / max(int(row.get('clicks', 0)), 1),
                    'countries': [],  # Will be populated from additional data if needed
                }
                result.append(creative_data)

            logger.info(f"Found {len(result)} creatives")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get creatives stats: {e}")
            return []

    async def get_creatives_report(
        self,
        period: ReportPeriod = ReportPeriod.YESTERDAY,
        buyer_id: Optional[str] = None,
        geo: Optional[str] = None,
        traffic_source_ids: Optional[List[str]] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get detailed creatives statistics with sub_id_4 as creative ID
        
        Returns list of creative stats including:
        - creative_id (from sub_id_4)
        - buyer_id (from sub_id_1)
        - geo/country
        - clicks, unique_clicks, conversions, deposits, revenue
        - uEPC (revenue per unique click)
        - active_days (days with 10+ clicks)
        """
        
        # Determine time range
        if period == ReportPeriod.CUSTOM and custom_start and custom_end:
            start_date = custom_start
            end_date = custom_end
        else:
            # Calculate dates based on period
            from datetime import datetime, timedelta
            now = datetime.now()
            
            if period == ReportPeriod.TODAY:
                start_date = now.strftime('%Y-%m-%d 00:00:00')
                end_date = now.strftime('%Y-%m-%d 23:59:59')
            elif period == ReportPeriod.YESTERDAY:
                yesterday = now - timedelta(days=1)
                start_date = yesterday.strftime('%Y-%m-%d 00:00:00')
                end_date = yesterday.strftime('%Y-%m-%d 23:59:59')
            elif period == ReportPeriod.LAST_3D:
                start_date = (now - timedelta(days=3)).strftime('%Y-%m-%d 00:00:00')
                end_date = now.strftime('%Y-%m-%d 23:59:59')
            elif period == ReportPeriod.LAST_7D:
                start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d 00:00:00')
                end_date = now.strftime('%Y-%m-%d 23:59:59')
            elif period == ReportPeriod.LAST_30D:
                start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
                end_date = now.strftime('%Y-%m-%d 23:59:59')
            else:
                start_date = (now - timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')
                end_date = now.strftime('%Y-%m-%d 23:59:59')
        
        try:
            logger.info(f"=== KEITARO CLIENT DEBUG ===")
            logger.info(f"get_creatives_report called with: period={period}, buyer_id={buyer_id}, geo={geo}, traffic_source_ids={traffic_source_ids}")
            logger.info(f"Date range: {start_date} - {end_date}")
            
            # FIRST REQUEST: Get main metrics without datetime for accurate aggregation
            main_report_params = {
                'metrics': ['clicks', 'global_unique_clicks', 'conversions', 'leads', 'sales', 'revenue'],
                'columns': ['sub_id_4', 'sub_id_1', 'country'],
                'filters': [
                    {
                        'name': 'datetime',
                        'operator': 'BETWEEN',
                        'expression': [start_date, end_date]
                    }
                ],
                'grouping': ['sub_id_4', 'sub_id_1', 'country'],
                'sort': [{'name': 'revenue', 'order': 'DESC'}],
                'limit': 10000
            }
            
            # Add buyer filter if specified
            if buyer_id:
                main_report_params['filters'].append({
                    'name': 'sub_id_1',
                    'operator': 'EQUALS',
                    'expression': buyer_id
                })
            
            # Add geo filter if specified
            if geo:
                main_report_params['filters'].append({
                    'name': 'country',
                    'operator': 'EQUALS',
                    'expression': geo
                })
            
            # Add traffic source filter if specified
            if traffic_source_ids:
                main_report_params['filters'].append({
                    'name': 'ts_id',
                    'operator': 'IN_LIST',
                    'expression': traffic_source_ids
                })
            
            logger.info(f"Getting creatives report: {start_date} - {end_date}")
            logger.info(f"Main report API params: {main_report_params}")
            
            # Get main report data (accurate metrics)
            data = await self._make_request('/admin_api/v1/report/build', method='POST', json=main_report_params)
            
            if not data or 'rows' not in data:
                logger.warning("No creatives data received from main API")
                logger.warning(f"Main API response: {data}")
                return []
            
            logger.info(f"Main API returned {len(data.get('rows', []))} raw rows")
            
            # SECOND REQUEST: Get active days data (with datetime grouping)
            active_days_params = {
                'metrics': ['clicks'],  # Just need clicks to count active days
                'columns': ['sub_id_4', 'datetime'],
                'filters': main_report_params['filters'].copy(),  # Same filters
                'grouping': ['sub_id_4', 'datetime'],
                'limit': 10000
            }
            
            logger.info(f"=== ACTIVE DAYS REQUEST ===")
            logger.info(f"Active days API params: {active_days_params}")
            
            active_days_data = await self._make_request('/admin_api/v1/report/build', method='POST', json=active_days_params)
            logger.info(f"Active days API response keys: {list(active_days_data.keys()) if active_days_data else 'None'}")
            
            # Process active days data to get unique dates per creative
            creative_active_days = {}
            if active_days_data and 'rows' in active_days_data:
                logger.info(f"Active days API returned {len(active_days_data['rows'])} rows")
                
                # Log sample rows for debugging
                if len(active_days_data['rows']) > 0:
                    sample_row = active_days_data['rows'][0]
                    logger.info(f"Sample active days row: {sample_row}")
                
                for row in active_days_data['rows']:
                    creative_id = row.get('sub_id_4', 'unknown')
                    if creative_id == 'unknown' or not creative_id:
                        continue
                    
                    datetime_str = row.get('datetime', '')
                    clicks = int(row.get('clicks', 0))
                    
                    if clicks > 0 and datetime_str:
                        # Extract date part
                        try:
                            date_part = datetime_str.split('T')[0] if 'T' in datetime_str else datetime_str.split(' ')[0]
                        except:
                            date_part = datetime_str
                        
                        if creative_id not in creative_active_days:
                            creative_active_days[creative_id] = set()
                        creative_active_days[creative_id].add(date_part)
                        
                        # Log tr32 specifically
                        if creative_id == 'tr32':
                            logger.info(f"tr32 active day found: date={date_part}, clicks={clicks}")
                
                # Log tr32 final count
                if 'tr32' in creative_active_days:
                    logger.info(f"tr32 total active days found: {len(creative_active_days['tr32'])}, dates: {sorted(creative_active_days['tr32'])}")
                else:
                    logger.warning("tr32 NOT FOUND in active days data")
                    
            else:
                logger.warning(f"No active days data received. Response: {active_days_data}")
            
            logger.info(f"Processed active days for {len(creative_active_days)} creatives")
            
            # TEMPORARY: Check if we got any active days data at all
            if not creative_active_days:
                logger.warning("FALLBACK: No active days data received, will use default value of 1 for all creatives")
            
            # Process and aggregate main data by creative (accurate metrics)
            creatives_data = {}
            processed_rows = 0
            skipped_rows = 0
            
            for row in data['rows']:
                creative_id = row.get('sub_id_4', 'unknown')
                # Skip rows with empty, null, or placeholder creative IDs
                if (creative_id == 'unknown' or not creative_id or 
                    creative_id in ['{sub_id_4}', 'null', '', ' '] or
                    str(creative_id).strip() == ''):
                    skipped_rows += 1
                    continue
                
                processed_rows += 1
                
                buyer = row.get('sub_id_1', 'unknown')
                # Skip rows with empty, null, or placeholder buyer IDs
                if (buyer == 'unknown' or not buyer or 
                    buyer in ['{sub_id_1}', 'null', '', ' '] or
                    str(buyer).strip() == ''):
                    buyer = 'unknown'
                
                country = row.get('country', 'unknown')
                clicks = int(row.get('clicks', 0))
                unique_clicks = int(row.get('global_unique_clicks', 0))
                
                # Initialize creative data if not exists
                if creative_id not in creatives_data:
                    creatives_data[creative_id] = {
                        'creative_id': creative_id,
                        'buyer_id': buyer,
                        'geos': set(),
                        'clicks': 0,
                        'unique_clicks': 0,
                        'conversions': 0,
                        'leads': 0,
                        'deposits': 0,  # sales = deposits
                        'revenue': 0.0
                    }
                
                # Aggregate data
                creatives_data[creative_id]['geos'].add(country)
                creatives_data[creative_id]['clicks'] += clicks
                creatives_data[creative_id]['unique_clicks'] += unique_clicks
                creatives_data[creative_id]['conversions'] += int(row.get('conversions', 0))
                leads_to_add = int(row.get('leads', 0))
                creatives_data[creative_id]['leads'] += leads_to_add
                creatives_data[creative_id]['deposits'] += int(row.get('sales', 0))
                creatives_data[creative_id]['revenue'] += float(row.get('revenue', 0))
                
                # Debug tr32 leads aggregation
                if creative_id == 'tr32':
                    logger.info(f"tr32 row: country={country}, leads={leads_to_add}, total_leads_so_far={creatives_data[creative_id]['leads']}")
            
            # Calculate metrics and format result
            result = []
            for creative_id, data in creatives_data.items():
                # Calculate uEPC
                uepc = data['revenue'] / data['unique_clicks'] if data['unique_clicks'] > 0 else 0
                
                # Calculate conversion rates
                dep_to_reg = (data['deposits'] / data['leads'] * 100) if data['leads'] > 0 else 0
                
                # Get active days from second API call
                active_days = len(creative_active_days.get(creative_id, set()))
                if active_days == 0:
                    active_days = 1  # Default to 1 if no dates tracked
                
                result.append({
                    'creative_id': creative_id,
                    'buyer_id': data['buyer_id'],
                    'geos': ', '.join(sorted(data['geos'])),
                    'clicks': data['clicks'],
                    'unique_clicks': data['unique_clicks'],
                    'conversions': data['conversions'],
                    'leads': data['leads'],
                    'deposits': data['deposits'],
                    'revenue': data['revenue'],
                    'dep_to_reg': dep_to_reg,
                    'uepc': uepc,
                    'active_days': active_days
                })
            
            # Don't sort here - let the service handle sorting
            logger.info(f"Processed {processed_rows} rows, skipped {skipped_rows} rows")
            logger.info(f"Final result: {len(result)} unique creatives")
            
            # Log tr32 details if found (user's case)
            tr32_result = next((r for r in result if r['creative_id'] == 'tr32'), None)
            if tr32_result:
                logger.info(f"tr32 in final result: leads={tr32_result['leads']}, active_days={tr32_result['active_days']}, revenue=${tr32_result['revenue']}")
                logger.info(f"tr32 from active_days_data: {len(creative_active_days.get('tr32', set()))} unique dates")
            else:
                logger.info("tr32 NOT FOUND in final result")
            
            # Also log TR36 details if found
            tr36_result = next((r for r in result if r['creative_id'] == 'TR36'), None)
            if tr36_result:
                logger.info(f"TR36 in final result: revenue=${tr36_result['revenue']}, unique_clicks={tr36_result['unique_clicks']}, uepc=${tr36_result['uepc']:.2f}")
            else:
                logger.info("TR36 NOT FOUND in final result")
                sample_ids = [r['creative_id'] for r in result[:5]]
                logger.info(f"Sample creative IDs in result: {sample_ids}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get creatives report: {e}")
            return []