"""
Google Sheets Reports Export Service
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import gspread
from google.oauth2.service_account import Credentials
import logging

from core.config import settings
from bot.services.reports import ReportsService

logger = logging.getLogger(__name__)


class GoogleSheetsReportsExporter:
    """Service for exporting reports to Google Sheets"""
    
    def __init__(self):
        self.credentials = self._get_credentials()
        self.gc = gspread.authorize(self.credentials)
        self.reports_service = ReportsService()
    
    def _get_credentials(self) -> Credentials:
        """Get Google service account credentials"""
        credentials_info = settings.google_credentials_dict
        credentials = Credentials.from_service_account_info(
            credentials_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return credentials
    
    def _format_period_name(self, period: str) -> str:
        """Format period name for display"""
        period_names = {
            "today": "Сегодня",
            "yesterday": "Вчера", 
            "last3days": "Последние 3 дня",
            "last7days": "Последние 7 дней",
            "last15days": "Последние 15 дней",
            "thismonth": "Этот месяц",
            "lastmonth": "Прошлый месяц"
        }
        return period_names.get(period, period)
    
    def _format_traffic_source(self, traffic_source: str) -> str:
        """Format traffic source name for display"""
        source_names = {
            "google": "Google",
            "fb": "Facebook"
        }
        return source_names.get(traffic_source, traffic_source)
    
    async def create_or_get_spreadsheet(self, sheet_name: str) -> gspread.Spreadsheet:
        """Create or get spreadsheet for reports"""
        try:
            # Try to open existing spreadsheet
            spreadsheet = self.gc.open(sheet_name)
            logger.info(f"Opened existing spreadsheet: {sheet_name}")
        except gspread.SpreadsheetNotFound:
            # Create new spreadsheet
            spreadsheet = self.gc.create(sheet_name)
            logger.info(f"Created new spreadsheet: {sheet_name}")
            
            # Share with the configured email if available
            if hasattr(settings, 'google_drive_shared_email') and settings.google_drive_shared_email:
                spreadsheet.share(settings.google_drive_shared_email, perm_type='user', role='writer')
                logger.info(f"Shared spreadsheet with: {settings.google_drive_shared_email}")
        
        return spreadsheet
    
    async def export_creatives_report(
        self,
        period: str,
        traffic_source: str = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Export creatives report to Google Sheets in CSV format"""
        logger.info(f"Exporting creatives report: period={period}, traffic_source={traffic_source}")
        
        try:
            # Get report data - we'll call Keitaro directly for full export
            from integrations.keitaro.client import KeitaroClient
            from core.enums import ReportPeriod
            
            # Convert period to appropriate format
            period_enum = self.reports_service._period_to_enum(period)
            custom_dates = self.reports_service._get_custom_dates(period)
            
            # Get traffic source filter if needed
            traffic_source_ids = None
            if traffic_source:
                traffic_source_ids = await self.reports_service._get_traffic_source_filter(traffic_source)
            
            async with KeitaroClient() as client:
                if custom_dates:
                    creatives_data = await client.get_creatives_report(
                        period=ReportPeriod.CUSTOM,
                        buyer_id=None,
                        geo=None, 
                        traffic_source_ids=traffic_source_ids,
                        custom_start=custom_dates[0],
                        custom_end=custom_dates[1]
                    )
                else:
                    creatives_data = await client.get_creatives_report(
                        period=period_enum,
                        buyer_id=None,
                        geo=None,
                        traffic_source_ids=traffic_source_ids
                    )
                
                # Sort by uEPC descending (like in the CSV example)
                creatives_data.sort(key=lambda x: x.get('uepc', 0), reverse=True)
            
            if not creatives_data:
                raise ValueError("Нет данных для экспорта")
            
            # Create spreadsheet name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            period_name = self._format_period_name(period)
            source_name = self._format_traffic_source(traffic_source) if traffic_source else "все источники"
            sheet_name = f"Отчет_креативы_{period_name}_{timestamp}"
            
            # Create/get spreadsheet
            spreadsheet = await self.create_or_get_spreadsheet(sheet_name)
            worksheet = spreadsheet.get_worksheet(0)
            
            # Clear existing content
            worksheet.clear()
            
            # Prepare header info (matching CSV format)
            header_info = [
                ["Период", f"за {period_name.lower()}", "", "", "", "", "", "", "", "", ""],
                ["ГЕО", "все гео", "", "", "", "", "", "", "", "", ""],  
                ["Баеры", "все баеры", "", "", "", "", "", "", "", "", ""],
                ["", "", "", "", "", "", "", "", "", "", ""],  # Empty row
            ]
            
            # Column headers (matching CSV format exactly)
            column_headers = [
                "ID крео",
                "ID баера", 
                "ГЕО",
                "Уник. клики",
                "Регистрации",
                "депозиты", 
                "Доход $",
                "Деп/Рег %",
                "uEPC $",
                "Активных дней",
                "Ссылка на крео"
            ]
            
            # Prepare all rows
            all_rows = header_info + [column_headers]
            
            # Add data rows
            for creative in creatives_data:
                # Calculate Деп/Рег % (deposits/registrations percentage)
                registrations = creative.get('leads', 0)
                deposits = creative.get('deposits', 0)  # Use 'deposits' field from Keitaro
                dep_reg_percent = f"{(deposits / registrations * 100):.0f}%" if registrations > 0 else "0%"
                
                row = [
                    creative.get('creative_id', ''),
                    creative.get('buyer_id', ''),
                    creative.get('geos', ''),  # Use 'geos' field from Keitaro (already formatted string)
                    creative.get('unique_clicks', 0),  # Use unique_clicks instead of clicks
                    registrations,
                    deposits,
                    f"{creative.get('revenue', 0):.1f}".replace('.', ','),  # Format like CSV with comma separator
                    dep_reg_percent,
                    f"{creative.get('uepc', 0):.2f}".replace('.', ','),  # Format like CSV with comma separator
                    creative.get('active_days', 1),
                    "Ссылка"  # Placeholder for creative link
                ]
                all_rows.append(row)
            
            # Write all data to sheet
            worksheet.update("A1", all_rows)
            
            # Format header info
            worksheet.format("A1:A3", {
                "textFormat": {"bold": True}
            })
            
            # Format column headers
            header_row = len(header_info) + 1
            worksheet.format(f"A{header_row}:K{header_row}", {
                "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9},
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "horizontalAlignment": "CENTER"
            })
            
            # Auto-resize columns
            worksheet.columns_auto_resize(0, len(column_headers))
            
            spreadsheet_url = spreadsheet.url
            logger.info(f"Creatives report exported successfully: {spreadsheet_url}")
            
            return spreadsheet_url
            
        except Exception as e:
            logger.error(f"Error exporting creatives report: {e}")
            raise
    
    async def export_buyers_report(
        self,
        period: str,
        traffic_source: str = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Export buyers report to Google Sheets"""
        logger.info(f"Exporting buyers report: period={period}, traffic_source={traffic_source}")
        
        try:
            # Get report data
            buyers_data = await self.reports_service.get_buyers_report(period, "all", filters, traffic_source)
            
            if not buyers_data:
                raise ValueError("Нет данных для экспорта")
            
            # Create spreadsheet name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            period_name = self._format_period_name(period)
            source_name = self._format_traffic_source(traffic_source) if traffic_source else "Все источники"
            sheet_name = f"Байеры_{source_name}_{period_name}_{timestamp}"
            
            # Create/get spreadsheet
            spreadsheet = await self.create_or_get_spreadsheet(sheet_name)
            worksheet = spreadsheet.get_worksheet(0)
            
            # Clear existing content
            worksheet.clear()
            
            # Prepare headers
            headers = [
                "Buyer ID",
                "Клики",
                "Регистрации", 
                "Продажи",
                "Доход ($)",
                "Конверсии",
                "EPC ($)",
                "CTR (%)",
                "CR (%)",
                "ROI (%)",
                "Расходы ($)",
                "ГЕО",
                "Офферы",
                "Количество креативов"
            ]
            
            # Prepare data rows
            rows = [headers]
            for buyer in buyers_data:
                row = [
                    buyer.get('buyer_id', ''),
                    buyer.get('clicks', 0),
                    buyer.get('leads', 0),
                    buyer.get('sales', 0),
                    round(buyer.get('revenue', 0), 2),
                    buyer.get('conversions', 0),
                    round(buyer.get('epc', 0), 3),
                    round(buyer.get('ctr', 0), 2),
                    round(buyer.get('cr', 0), 2),
                    round(buyer.get('roi', 0), 2),
                    round(buyer.get('cost', 0), 2),
                    ', '.join(buyer.get('countries', [])),
                    ', '.join(buyer.get('offers', [])),
                    buyer.get('creatives_count', 0)
                ]
                rows.append(row)
            
            # Write data to sheet
            worksheet.update("A1", rows)
            
            # Format headers
            worksheet.format("A1:N1", {
                "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9},
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "horizontalAlignment": "CENTER"
            })
            
            # Auto-resize columns
            worksheet.columns_auto_resize(0, len(headers))
            
            # Add summary info
            summary_start_row = len(rows) + 3
            total_revenue = sum(b.get('revenue', 0) for b in buyers_data)
            total_clicks = sum(b.get('clicks', 0) for b in buyers_data)
            total_leads = sum(b.get('leads', 0) for b in buyers_data)
            avg_epc = total_revenue / total_clicks if total_clicks > 0 else 0
            
            summary_data = [
                ["СВОДКА ПО ОТЧЕТУ", ""],
                ["Период", period_name],
                ["Источник трафика", source_name],
                ["Количество байеров", len(buyers_data)],
                ["Общий доход ($)", round(total_revenue, 2)],
                ["Общие клики", total_clicks],
                ["Общие регистрации", total_leads],
                ["Средний EPC ($)", round(avg_epc, 3)],
                ["Дата экспорта", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ]
            
            # Write summary
            for i, summary_row in enumerate(summary_data):
                cell_range = f"A{summary_start_row + i}:B{summary_start_row + i}"
                worksheet.update(cell_range, [summary_row])
            
            # Format summary header
            worksheet.format(f"A{summary_start_row}:B{summary_start_row}", {
                "backgroundColor": {"red": 0.9, "green": 0.6, "blue": 0.2},
                "textFormat": {"bold": True}
            })
            
            spreadsheet_url = spreadsheet.url
            logger.info(f"Buyers report exported successfully: {spreadsheet_url}")
            
            return spreadsheet_url
            
        except Exception as e:
            logger.error(f"Error exporting buyers report: {e}")
            raise
    
    async def export_geo_report(
        self,
        period: str,
        traffic_source: str = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Export GEO report to Google Sheets"""
        logger.info(f"Exporting GEO report: period={period}, traffic_source={traffic_source}")
        
        try:
            # Get report data
            geo_data = await self.reports_service.get_geo_report(period, filters, traffic_source)
            
            if not geo_data:
                raise ValueError("Нет данных для экспорта")
            
            # Create spreadsheet name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            period_name = self._format_period_name(period)
            source_name = self._format_traffic_source(traffic_source) if traffic_source else "Все источники"
            sheet_name = f"ГЕО_{source_name}_{period_name}_{timestamp}"
            
            # Create/get spreadsheet
            spreadsheet = await self.create_or_get_spreadsheet(sheet_name)
            worksheet = spreadsheet.get_worksheet(0)
            
            # Clear existing content
            worksheet.clear()
            
            # Prepare headers
            headers = [
                "ГЕО",
                "Клики",
                "Регистрации",
                "Продажи", 
                "Доход ($)",
                "Конверсии",
                "EPC ($)",
                "CTR (%)",
                "CR (%)",
                "Количество байеров"
            ]
            
            # Prepare data rows
            rows = [headers]
            for geo in geo_data:
                row = [
                    geo.get('country', ''),
                    geo.get('clicks', 0),
                    geo.get('leads', 0),
                    geo.get('sales', 0),
                    round(geo.get('revenue', 0), 2),
                    geo.get('conversions', 0),
                    round(geo.get('epc', 0), 3),
                    round(geo.get('ctr', 0), 2),
                    round(geo.get('cr', 0), 2),
                    geo.get('buyers_count', 0)
                ]
                rows.append(row)
            
            # Write data to sheet
            worksheet.update("A1", rows)
            
            # Format headers
            worksheet.format("A1:J1", {
                "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9},
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "horizontalAlignment": "CENTER"
            })
            
            # Auto-resize columns
            worksheet.columns_auto_resize(0, len(headers))
            
            # Add summary
            summary_start_row = len(rows) + 3
            summary_data = [
                ["СВОДКА ПО ОТЧЕТУ", ""],
                ["Период", period_name],
                ["Источник трафика", source_name],
                ["Количество ГЕО", len(geo_data)],
                ["Общий доход ($)", sum(g.get('revenue', 0) for g in geo_data)],
                ["Общие клики", sum(g.get('clicks', 0) for g in geo_data)],
                ["Общие регистрации", sum(g.get('leads', 0) for g in geo_data)],
                ["Дата экспорта", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ]
            
            # Write summary
            for i, summary_row in enumerate(summary_data):
                cell_range = f"A{summary_start_row + i}:B{summary_start_row + i}"
                worksheet.update(cell_range, [summary_row])
            
            # Format summary header
            worksheet.format(f"A{summary_start_row}:B{summary_start_row}", {
                "backgroundColor": {"red": 0.9, "green": 0.6, "blue": 0.2},
                "textFormat": {"bold": True}
            })
            
            spreadsheet_url = spreadsheet.url
            logger.info(f"GEO report exported successfully: {spreadsheet_url}")
            
            return spreadsheet_url
            
        except Exception as e:
            logger.error(f"Error exporting GEO report: {e}")
            raise