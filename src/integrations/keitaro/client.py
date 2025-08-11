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
        # Создаем коннектор с правильной конфигурацией
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            # Дополнительно даем время на очистку соединений
            await asyncio.sleep(0.1)
            
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
                    # Последние 7 дней включая сегодня (6 дней назад + сегодня = 7 дней)
                    start_date = (now - timedelta(days=6)).strftime('%Y-%m-%d 00:00:00')
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
                    # Последние 7 дней включая сегодня (6 дней назад + сегодня = 7 дней)
                    start_date = (now - timedelta(days=6)).strftime('%Y-%m-%d 00:00:00')
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
                        # Последние 7 дней включая сегодня (6 дней назад + сегодня = 7 дней)
                        start_date = (now - timedelta(days=6)).strftime('%Y-%m-%d 00:00:00')
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
                        # Последние 7 дней включая сегодня (6 дней назад + сегодня = 7 дней)
                        start_date = (now - timedelta(days=6)).strftime('%Y-%m-%d 00:00:00')
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
                # Последние 7 дней - от 7 дней назад до сегодня (включительно)
                start_date = (now - timedelta(days=6)).strftime('%Y-%m-%d 00:00:00')  
                end_date = now.strftime('%Y-%m-%d 23:59:59')
                logger.info(f"LAST_7D period: {start_date} to {end_date} (last 7 days including today)")
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
            
            # ВАЖНО: Логируем точные даты для проверки исправления
            from datetime import datetime
            now_debug = datetime.now()
            logger.info(f"DEBUG: Current time is {now_debug}")
            logger.info(f"DEBUG: For LAST_7D we should use dates from {(now_debug - timedelta(days=6)).strftime('%Y-%m-%d')} to {now_debug.strftime('%Y-%m-%d')} (last 7 days including today)")
            logger.info(f"DEBUG: ACTUAL dates being used: {start_date} to {end_date}")
            
            # FIRST REQUEST: Get main metrics without datetime for accurate aggregation
            # Try without country grouping to avoid splitting data across countries
            main_report_params = {
                'metrics': ['clicks', 'global_unique_clicks', 'conversions', 'leads', 'sales', 'revenue'],
                'columns': ['sub_id_4', 'sub_id_1'],  # Remove country to get unified data
                'filters': [
                    {
                        'name': 'datetime',
                        'operator': 'BETWEEN',
                        'expression': [start_date, end_date]
                    }
                ],
                'grouping': ['sub_id_4', 'sub_id_1'],  # Remove country grouping
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
            # Note: Some rows have empty sub_id_4, so we need to be more flexible
            active_days_params = {
                'metrics': ['clicks'],  # Just need clicks to count active days
                'columns': ['sub_id_4', 'datetime'],
                'filters': main_report_params['filters'].copy(),  # Same filters
                'grouping': ['sub_id_4', 'datetime'],
                'limit': 10000
            }
            
            # Also try to get data with only sub_id_4 filter (no empty values)
            for filter_item in active_days_params['filters']:
                if filter_item['name'] == 'datetime':
                    continue  # Keep datetime filter
                elif filter_item['name'] == 'ts_id':
                    continue  # Keep traffic source filter
            
            # Add filter to exclude empty sub_id_4 values
            active_days_params['filters'].append({
                'name': 'sub_id_4',
                'operator': 'NOT_EQUAL',  # Correct operator name
                'expression': ''
            })
            
            logger.info(f"=== ACTIVE DAYS REQUEST ===")
            logger.info(f"Active days API params: {active_days_params}")
            logger.info(f"SYNC CHECK: Active days using same dates: {start_date} - {end_date}")
            
            active_days_data = await self._make_request('/admin_api/v1/report/build', method='POST', json=active_days_params)
            logger.info(f"Active days API response keys: {list(active_days_data.keys()) if active_days_data else 'None'}")
            
            # ИСПРАВЛЕНО: Process active days data - считаем КОЛИЧЕСТВО кликов за день, а не отдельные строки
            creative_active_days = {}
            creative_daily_clicks = {}  # Счетчик кликов по дням для каждого креатива
            
            if active_days_data and 'rows' in active_days_data:
                logger.info(f"Active days API returned {len(active_days_data['rows'])} rows")
                
                # Log sample rows for debugging
                if len(active_days_data['rows']) > 0:
                    sample_row = active_days_data['rows'][0]
                    logger.info(f"Sample active days row: {sample_row}")
                
                # ПЕРВЫЙ ПРОХОД: Считаем клики по дням для каждого креатива
                for row in active_days_data['rows']:
                    creative_id = row.get('sub_id_4', 'unknown')
                    # Skip empty or invalid creative IDs
                    if (creative_id == 'unknown' or not creative_id or 
                        creative_id in ['', ' ', 'null', '{sub_id_4}'] or
                        str(creative_id).strip() == ''):
                        continue
                    
                    # Сохраняем исходный регистр из API
                    creative_id = str(creative_id)
                    
                    datetime_str = row.get('datetime', '')
                    if not datetime_str:
                        continue
                        
                    # Extract date part
                    try:
                        date_part = datetime_str.split('T')[0] if 'T' in datetime_str else datetime_str.split(' ')[0]
                    except:
                        continue
                        
                    # Инициализируем структуру данных
                    if creative_id not in creative_daily_clicks:
                        creative_daily_clicks[creative_id] = {}
                    if date_part not in creative_daily_clicks[creative_id]:
                        creative_daily_clicks[creative_id][date_part] = 0
                        
                    # Каждая строка = 1 клик
                    creative_daily_clicks[creative_id][date_part] += 1
                
                # ВТОРОЙ ПРОХОД: Определяем активные дни (10+ кликов за день)
                for creative_id, daily_data in creative_daily_clicks.items():
                    for date_part, total_clicks in daily_data.items():
                        # ДИАГНОСТИКА: логируем tr32
                        if creative_id == 'tr32':
                            logger.info(f"TR32 DAILY BREAKDOWN: date={date_part}, total_clicks={total_clicks}, is_active={total_clicks >= 10}")
                            logger.info(f"  -> Adding to active days: {total_clicks >= 10}")
                        
                        if total_clicks >= 10:
                            if creative_id not in creative_active_days:
                                creative_active_days[creative_id] = set()
                            creative_active_days[creative_id].add(date_part)
                            
                            # Log tr32 specifically  
                            if creative_id == 'tr32':
                                logger.info(f"tr32 ACTIVE day confirmed: {date_part} with {total_clicks} clicks")
                
                # ДЕТАЛЬНАЯ ДИАГНОСТИКА АКТИВНЫХ ДНЕЙ TR32
                logger.info(f"=== TR32 ACTIVE DAYS DIAGNOSTICS ===")
                
                # ПОИСК TR32 по всем возможным sub_id_4 значениям
                logger.info(f"Searching for TR32 in active days data...")
                tr32_possible_ids = set()  # Соберем все возможные ID для tr32
                
                # НОВАЯ ДИАГНОСТИКА: Проверим сколько дней tr32 имел клики БЕЗ порога  
                tr32_all_days_clicks = {}
                tr32_raw_rows_found = 0
                for row in active_days_data.get('rows', []):
                    creative_id = row.get('sub_id_4', 'unknown')
                    
                    # Ищем tr32 (маленькими буквами) - Keitaro чувствителен к регистру!
                    if str(creative_id) == 'tr32':
                        tr32_raw_rows_found += 1
                        tr32_possible_ids.add(creative_id)
                        datetime_str = row.get('datetime', '')
                        clicks = int(row.get('clicks', 0))
                        
                        # ДЕТАЛЬНЫЙ ЛОГ каждой строки TR32
                        logger.info(f"TR32 raw row #{tr32_raw_rows_found}: datetime='{datetime_str}', clicks={clicks}")
                        
                        if datetime_str:
                            date_part = datetime_str.split('T')[0] if 'T' in datetime_str else datetime_str.split(' ')[0]
                            logger.info(f"  -> extracted date_part: '{date_part}'")
                            
                            if date_part not in tr32_all_days_clicks:
                                tr32_all_days_clicks[date_part] = 0
                            tr32_all_days_clicks[date_part] += clicks
                            logger.info(f"  -> date_part '{date_part}' now has total {tr32_all_days_clicks[date_part]} clicks")
                
                logger.info(f"TR32 ANALYSIS: Found {tr32_raw_rows_found} raw rows in active_days_data")
                
                # Логируем все уникальные sub_id_4 с большим количеством кликов (подозрительные на TR32)
                high_click_candidates = {}
                for row in active_days_data.get('rows', []):
                    creative_id = row.get('sub_id_4', 'unknown')
                    clicks = int(row.get('clicks', 0))
                    datetime_str = row.get('datetime', '')
                    
                    if clicks >= 50:  # Подозрительно высокие клики могут быть TR32
                        if creative_id not in high_click_candidates:
                            high_click_candidates[creative_id] = {'total_clicks': 0, 'days': set()}
                        high_click_candidates[creative_id]['total_clicks'] += clicks
                        if datetime_str:
                            date_part = datetime_str.split('T')[0] if 'T' in datetime_str else datetime_str.split(' ')[0]
                            high_click_candidates[creative_id]['days'].add(date_part)
                
                logger.info(f"TR32 possible IDs found: {tr32_possible_ids}")
                logger.info(f"High-click candidates (50+ clicks per row): {dict(list(high_click_candidates.items())[:5])}")
                
                if tr32_all_days_clicks:
                    logger.info(f"TR32 ALL days with clicks (no threshold): {tr32_all_days_clicks}")
                    logger.info(f"TR32 days with clicks >= 10: {[d for d, c in tr32_all_days_clicks.items() if c >= 10]}")
                    logger.info(f"TR32 days with clicks < 10: {[d for d, c in tr32_all_days_clicks.items() if c < 10]}")
                    logger.info(f"TR32 total clicks all days: {sum(tr32_all_days_clicks.values())}")
                else:
                    logger.warning("TR32 NOT FOUND in active days raw data at all!")
                
                # Log tr32 final count with detailed date analysis
                if 'tr32' in creative_active_days:
                    tr32_dates = sorted(creative_active_days['tr32'])
                    logger.info(f"tr32 total active days found (with 10+ threshold): {len(tr32_dates)}")
                    logger.info(f"tr32 active dates (10+ clicks): {tr32_dates}")
                else:
                    logger.warning("tr32 NOT FOUND in active days data (10+ clicks)")
                    
                logger.info(f"=== END TR32 ACTIVE DAYS DIAGNOSTICS ===")
                    
            else:
                logger.warning(f"No active days data received. Response: {active_days_data}")
            
            logger.info(f"Processed active days for {len(creative_active_days)} creatives")
            
            # TEMPORARY: Check if we got any active days data at all
            if not creative_active_days:
                logger.warning("FALLBACK: No active days data received, will use default value of 1 for all creatives")
            
            # THIRD REQUEST: Get country information for creatives (separate to avoid data splitting)
            geo_params = {
                'metrics': ['clicks'],  # Just need minimal data
                'columns': ['sub_id_4', 'country'],
                'filters': main_report_params['filters'].copy(),  # Same filters as main
                'grouping': ['sub_id_4', 'country'],
                'limit': 10000
            }
            
            logger.info(f"=== GEO REQUEST ===")
            logger.info(f"Geo API params: {geo_params}")
            logger.info(f"SYNC CHECK: Geo using same dates: {start_date} - {end_date}")
            
            geo_data = await self._make_request('/admin_api/v1/report/build', method='POST', json=geo_params)
            
            # Process geo data to get countries per creative
            creative_countries = {}
            if geo_data and 'rows' in geo_data:
                logger.info(f"Geo API returned {len(geo_data['rows'])} rows")
                for row in geo_data['rows']:
                    creative_id = row.get('sub_id_4', 'unknown')
                    if (creative_id == 'unknown' or not creative_id or 
                        creative_id in ['', ' ', 'null', '{sub_id_4}'] or
                        str(creative_id).strip() == ''):
                        continue
                        
                    country = row.get('country', 'unknown')
                    if country and country != 'unknown':
                        if creative_id not in creative_countries:
                            creative_countries[creative_id] = set()
                        creative_countries[creative_id].add(country)
                        
                        # Log tr32 and TR36 countries from clicks
                        if creative_id in ['tr32', 'TR36']:
                            logger.info(f"{creative_id} CLICK country found: {country}")
            else:
                logger.warning("No geo data received")
                
            logger.info(f"Processed geo data for {len(creative_countries)} creatives")
            
            # FOURTH REQUEST: Get accurate leads count using conversions log (for validation) + geo data
            conversions_params = {
                "limit": 10000,
                "columns": ["sub_id_4", "sub_id_1", "status", "country"],
                "filters": [
                    {
                        "name": "postback_datetime",
                        "operator": "BETWEEN",
                        "expression": [start_date, end_date]
                    }
                ],
                "sort": [{"name": "postback_datetime", "order": "DESC"}]
            }
            
            # Add same filters as main request
            if buyer_id:
                conversions_params['filters'].append({
                    'name': 'sub_id_1',
                    'operator': 'EQUALS',
                    'expression': buyer_id
                })
            
            if geo:
                conversions_params['filters'].append({
                    'name': 'country',
                    'operator': 'EQUALS',
                    'expression': geo
                })
            
            if traffic_source_ids:
                conversions_params['filters'].append({
                    'name': 'ts_id',
                    'operator': 'IN_LIST',
                    'expression': traffic_source_ids
                })
            
            logger.info(f"=== CONVERSIONS LOG REQUEST (for validation) ===")
            logger.info(f"Conversions API params: {conversions_params}")
            logger.info(f"SYNC CHECK: Conversions using same dates: {start_date} - {end_date}")
            
            conversions_data = await self._make_request('/admin_api/v1/conversions/log', method='POST', json=conversions_params)
            
            # Process conversions log to get accurate lead counts
            conversions_leads = {}
            if conversions_data:
                rows = conversions_data.get('rows', []) if isinstance(conversions_data, dict) else conversions_data if isinstance(conversions_data, list) else []
                logger.info(f"Conversions log API returned {len(rows)} conversions")
                
                for row in rows:
                    creative_id = row.get('sub_id_4', 'unknown')
                    if (creative_id == 'unknown' or not creative_id or 
                        creative_id in ['{sub_id_4}', 'null', '', ' '] or
                        str(creative_id).strip() == ''):
                        continue
                    
                    status = row.get('status', '')
                    if status == 'lead':
                        if creative_id not in conversions_leads:
                            conversions_leads[creative_id] = 0
                        conversions_leads[creative_id] += 1
                        
                        # Log tr32 specifically
                        if creative_id == 'tr32':
                            logger.info(f"tr32 lead found in conversions log: total_so_far={conversions_leads[creative_id]}")
                
                # ДЕТАЛЬНАЯ ДИАГНОСТИКА ДЛЯ TR32
                logger.info(f"=== TR32 DIAGNOSTICS START ===")
                logger.info(f"Total conversions log rows: {len(rows)}")
                
                # Подсчитаем tr32 во всех статусах
                tr32_all_statuses = {}
                tr32_buyers = set()
                tr32_dates = set()
                for row in rows:
                    creative_id = row.get('sub_id_4', 'unknown')
                    if creative_id == 'tr32':
                        status = row.get('status', 'unknown')
                        buyer = row.get('sub_id_1', 'unknown')
                        postback_date = row.get('postback_datetime', '')
                        if postback_date:
                            tr32_dates.add(postback_date.split(' ')[0])
                        tr32_buyers.add(buyer)
                        if status not in tr32_all_statuses:
                            tr32_all_statuses[status] = 0
                        tr32_all_statuses[status] += 1
                
                logger.info(f"TR32 in conversions log by status: {tr32_all_statuses}")
                logger.info(f"TR32 buyers in conversions: {tr32_buyers}")
                logger.info(f"TR32 dates in conversions: {sorted(tr32_dates)}")
                logger.info(f"TR32 total conversions (all statuses): {sum(tr32_all_statuses.values())}")
                
                # Log tr32 final count from conversions log
                if 'tr32' in conversions_leads:
                    logger.info(f"tr32 CONVERSIONS LOG total leads: {conversions_leads['tr32']}")
                else:
                    logger.warning("tr32 NOT FOUND in conversions log leads")
                
                logger.info(f"=== TR32 DIAGNOSTICS END ===")
                
                # ОБРАБОТКА ГЕО ДАННЫХ ИЗ КОНВЕРСИЙ
                # Переопределяем creative_countries на основе конверсий вместо кликов
                logger.info(f"Processing {len(rows)} conversion rows for geo extraction...")
                creative_countries_from_conversions = {}
                tr36_all_rows = []
                
                for row in rows:
                    creative_id = row.get('sub_id_4', 'unknown')
                    
                    # Собираем все строки TR36 для диагностики
                    if creative_id == 'TR36':
                        tr36_all_rows.append({
                            'creative_id': creative_id,
                            'status': row.get('status', 'unknown'),
                            'country': row.get('country', 'unknown'),
                            'postback_datetime': row.get('postback_datetime', 'unknown')
                        })
                    
                    if (creative_id == 'unknown' or not creative_id or 
                        creative_id in ['{sub_id_4}', 'null', '', ' '] or
                        str(creative_id).strip() == ''):
                        continue
                    
                    # Берем только конверсии (lead, sale), не все записи
                    status = row.get('status', '')
                    if status not in ['lead', 'sale']:
                        continue
                        
                    country = row.get('country', 'unknown')
                    if country and country != 'unknown':
                        if creative_id not in creative_countries_from_conversions:
                            creative_countries_from_conversions[creative_id] = set()
                        creative_countries_from_conversions[creative_id].add(country)
                        
                        # Log tr32 and TR36 conversion countries
                        if creative_id in ['tr32', 'TR36']:
                            logger.info(f"{creative_id} conversion country: {country} (status: {status})")
                
                # TR36 диагностика
                logger.info(f"=== TR36 DIAGNOSTICS START ===")
                logger.info(f"TR36 total rows found in conversions: {len(tr36_all_rows)}")
                if tr36_all_rows:
                    for row in tr36_all_rows[:5]:  # Показываем первые 5 строк
                        logger.info(f"TR36 row: {row}")
                    if 'TR36' in creative_countries_from_conversions:
                        logger.info(f"TR36 countries from conversions: {creative_countries_from_conversions['TR36']}")
                    else:
                        logger.warning("TR36 NOT FOUND in creative_countries_from_conversions")
                logger.info(f"=== TR36 DIAGNOSTICS END ===")
                
                # Используем гео данные из конверсий вместо кликов
                logger.info(f"GEO FROM CONVERSIONS: {len(creative_countries_from_conversions)} creatives have conversion geo data")
                if creative_countries_from_conversions:
                    creative_countries = creative_countries_from_conversions
                    logger.info("✅ Using geo data from CONVERSIONS instead of clicks")
                    for creative_id, countries in creative_countries.items():
                        if creative_id in ['tr32', 'TR36']:
                            logger.info(f"{creative_id} FINAL geo from conversions: {countries}")
                else:
                    logger.info("⚠️ No geo data from conversions, falling back to clicks data")
            else:
                logger.warning("No conversions log data received")
            
            # Process and aggregate main data by creative (accurate metrics)
            creatives_data = {}
            processed_rows = 0
            skipped_rows = 0
            tr32_rows_count = 0
            
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
                
                clicks = int(row.get('clicks', 0))
                unique_clicks = int(row.get('global_unique_clicks', 0))
                leads_to_add = int(row.get('leads', 0))
                
                # Count tr32 rows to see if we're missing data
                if creative_id == 'tr32':
                    tr32_rows_count += 1
                    original_sub_id_4 = row.get('sub_id_4', 'unknown')
                    logger.info(f"tr32 RAW row #{tr32_rows_count}: buyer={buyer}, clicks={clicks}, unique_clicks={unique_clicks}, leads={leads_to_add}, revenue={row.get('revenue', 0)}")
                    logger.info(f"tr32 ORIGINAL sub_id_4: '{original_sub_id_4}' (before normalization)")
                    logger.info(f"tr32 NORMALIZED creative_id: '{creative_id}' (after normalization)")
                
                # Initialize creative data if not exists
                if creative_id not in creatives_data:
                    creatives_data[creative_id] = {
                        'creative_id': creative_id,
                        'buyer_id': buyer,
                        'geos': set(),  # Will be populated separately
                        'clicks': 0,
                        'unique_clicks': 0,
                        'conversions': 0,
                        'leads': 0,
                        'deposits': 0,  # sales = deposits
                        'revenue': 0.0
                    }
                
                # Aggregate data (no country info in this request)
                creatives_data[creative_id]['clicks'] += clicks
                creatives_data[creative_id]['unique_clicks'] += unique_clicks
                creatives_data[creative_id]['conversions'] += int(row.get('conversions', 0))
                creatives_data[creative_id]['leads'] += leads_to_add
                creatives_data[creative_id]['deposits'] += int(row.get('sales', 0))
                creatives_data[creative_id]['revenue'] += float(row.get('revenue', 0))
                
                # Debug tr32 leads aggregation
                if creative_id == 'tr32':
                    logger.info(f"tr32 AGGREGATED after row #{tr32_rows_count}: total_leads={creatives_data[creative_id]['leads']}, total_revenue={creatives_data[creative_id]['revenue']}")
            
            logger.info(f"tr32 processing summary: found {tr32_rows_count} raw rows for tr32")
            
            # Calculate metrics and format result
            result = []
            for creative_id, data in creatives_data.items():
                # Calculate uEPC
                uepc = data['revenue'] / data['unique_clicks'] if data['unique_clicks'] > 0 else 0
                
                # Calculate conversion rates
                dep_to_reg = (data['deposits'] / data['leads'] * 100) if data['leads'] > 0 else 0
                
                # Get active days from second API call
                active_days = len(creative_active_days.get(creative_id, set()))
                
                # ДИАГНОСТИКА: проверим сопоставление ID для tr32
                if creative_id == 'tr32':
                    logger.info(f"tr32 ACTIVE DAYS LOOKUP: looking for '{creative_id}' in creative_active_days")
                    logger.info(f"tr32 Available keys in creative_active_days: {list(creative_active_days.keys())[:10]}")
                    logger.info(f"tr32 Found {active_days} active days")
                
                if active_days == 0:
                    active_days = 1  # Default to 1 if no dates tracked
                
                # Get countries from third API call
                countries = creative_countries.get(creative_id, set())
                geos_string = ', '.join(sorted(countries)) if countries else 'Unknown'
                
                # ИСПРАВЛЕНИЕ 2: Всегда используем conversions log как единственный источник истины для регистраций
                conversions_log_leads = conversions_leads.get(creative_id, 0)
                final_leads = conversions_log_leads if conversions_log_leads > 0 else data['leads']
                
                # Логируем расхождения для диагностики
                if conversions_log_leads != data['leads']:
                    logger.info(f"{creative_id} LEADS: report_api={data['leads']}, conversions_log={conversions_log_leads}, using_final={final_leads}")
                    if creative_id == 'tr32':
                        logger.info(f"tr32 CRITICAL: Using conversions_log as single source of truth")
                
                # Recalculate dep_to_reg with final leads
                dep_to_reg = (data['deposits'] / final_leads * 100) if final_leads > 0 else 0
                
                result.append({
                    'creative_id': creative_id,
                    'buyer_id': data['buyer_id'],
                    'geos': geos_string,
                    'clicks': data['clicks'],
                    'unique_clicks': data['unique_clicks'],
                    'conversions': data['conversions'],
                    'leads': final_leads,  # Use the more accurate count
                    'deposits': data['deposits'],
                    'revenue': data['revenue'],
                    'dep_to_reg': dep_to_reg,
                    'uepc': uepc,
                    'active_days': active_days
                })
            
            # Don't sort here - let the service handle sorting
            logger.info(f"Processed {processed_rows} rows, skipped {skipped_rows} rows")
            logger.info(f"Final result: {len(result)} unique creatives")
            
            # ФИНАЛЬНАЯ ДИАГНОСТИКА TR32
            logger.info(f"=== TR32 FINAL DIAGNOSTICS ===")
            
            # Log tr32 details if found (user's case)
            tr32_result = next((r for r in result if r['creative_id'] == 'tr32'), None)
            if tr32_result:
                logger.info(f"TR32 FINAL RESULT:")
                logger.info(f"  - unique_clicks: {tr32_result['unique_clicks']} (ожидается 317)")
                logger.info(f"  - leads: {tr32_result['leads']} (ожидается 120)")
                logger.info(f"  - deposits: {tr32_result['deposits']} (ожидается 17)")
                logger.info(f"  - revenue: ${tr32_result['revenue']} (ожидается $2115)")
                logger.info(f"  - active_days: {tr32_result['active_days']} (ожидается 2)")
                logger.info(f"  - uepc: ${tr32_result['uepc']:.2f}")
                
                # Сравнение источников данных
                logger.info(f"TR32 DATA SOURCES COMPARISON:")
                logger.info(f"  - Report API leads: {creatives_data.get('tr32', {}).get('leads', 0)}")
                logger.info(f"  - Conversions Log leads: {conversions_leads.get('tr32', 0)}")
                logger.info(f"  - Final used leads: {tr32_result['leads']}")
                logger.info(f"  - Active days from set: {len(creative_active_days.get('tr32', set()))}")
            else:
                logger.warning("TR32 NOT FOUND in final result!")
                logger.info(f"Available creative IDs: {[r['creative_id'] for r in result[:10]]}")
            
            logger.info(f"=== END TR32 FINAL DIAGNOSTICS ===")
            
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