"""
Клавиатуры для системы отчетов
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Optional, Dict, Any
from core.enums import ReportPeriod


class ReportsKeyboards:
    """Класс для создания клавиатур системы отчетов"""
    
    @staticmethod
    def main_reports_menu() -> InlineKeyboardMarkup:
        """Главное меню отчетов"""
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text="📊 Dashboard Сводка", 
                callback_data="reports_dashboard"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="👥 Отчет по байерам", 
                callback_data="reports_buyers"
            ),
            InlineKeyboardButton(
                text="🌍 Отчет по ГЕО", 
                callback_data="reports_geo"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🎨 Отчет по креативам", 
                callback_data="reports_creatives"
            ),
            InlineKeyboardButton(
                text="🎯 Отчет по офферам", 
                callback_data="reports_offers"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🏠 Главное меню", 
                callback_data="main_menu"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def period_selection(report_type: str, traffic_source: str = None, back_data: str = None) -> InlineKeyboardMarkup:
        """Выбор временного периода"""
        builder = InlineKeyboardBuilder()
        
        periods = [
            ("📅 Сегодня", "today"),
            ("📅 Вчера", "yesterday"),
            ("📅 Последние 3 дня", "last3days"),
            ("📅 Последние 7 дней", "last7days"),
            ("📅 Последние 15 дней", "last15days"),
            ("📅 Текущий месяц", "thismonth"),
            ("📅 Предыдущий месяц", "lastmonth")
        ]
        
        for text, period in periods:
            if traffic_source:
                # Новый формат с источником трафика
                callback_data = f"period_{report_type}_{traffic_source}_{period}"
            else:
                # Старый формат для совместимости
                callback_data = f"period_{report_type}_{period}"
                
            builder.row(
                InlineKeyboardButton(
                    text=text,
                    callback_data=callback_data
                )
            )
        
        # Кнопка назад
        if back_data:
            back_callback = back_data
        elif traffic_source:
            # Назад к выбору источника трафика
            back_callback = f"trafficsrc_{report_type}"
        else:
            # Назад к главному меню отчетов
            back_callback = "reports_main"
            
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=back_callback
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def traffic_source_selection(report_type: str) -> InlineKeyboardMarkup:
        """Выбор источника трафика"""
        builder = InlineKeyboardBuilder()
        
        # Источники трафика
        builder.row(
            InlineKeyboardButton(
                text="🔍 Google",
                callback_data=f"trafficsrc_{report_type}_google"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="📱 FB",
                callback_data=f"trafficsrc_{report_type}_fb"
            )
        )
        
        # Кнопка назад к выбору типа отчета
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="reports_main"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def buyers_filters(period: str, traffic_source: str = None, breadcrumbs: str = "") -> InlineKeyboardMarkup:
        """Фильтры для отчета по байерам"""
        builder = InlineKeyboardBuilder()
        
        bc = f"_{breadcrumbs}" if breadcrumbs else ""
        ts = f"_{traffic_source}" if traffic_source else ""
        
        builder.row(
            InlineKeyboardButton(
                text="👥 Все байеры",
                callback_data=f"buyers_all_{period}{ts}{bc}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🎯 Выбрать байера",
                callback_data=f"buyers_select_{period}{ts}{bc}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🌐 Весь трафик",
                callback_data=f"buyers_traffic_{period}{ts}{bc}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🌍 В разрезе ГЕО",
                callback_data=f"buyers_geo_{period}{ts}{bc}"
            ),
            InlineKeyboardButton(
                text="🎯 В разрезе офферов",
                callback_data=f"buyers_offers_{period}{ts}{bc}"
            )
        )
        
        # Кнопка назад
        if traffic_source:
            back_callback = f"trafficsrc_buyers_{traffic_source}"  # Возвращаемся к выбору периода
        else:
            back_callback = "reports_buyers"  # Возвращаемся к выбору источника
            
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=back_callback
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def geo_filters(period: str, breadcrumbs: str = "") -> InlineKeyboardMarkup:
        """Фильтры для отчета по ГЕО"""
        builder = InlineKeyboardBuilder()
        
        bc = f"_{breadcrumbs}" if breadcrumbs else ""
        
        builder.row(
            InlineKeyboardButton(
                text="🌍 Все ГЕО",
                callback_data=f"geo_all_{period}{bc}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🎯 Выбрать ГЕО",
                callback_data=f"geo_select_{period}{bc}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="👥 По всем байерам",
                callback_data=f"geo_allbuyers_{period}{bc}"
            ),
            InlineKeyboardButton(
                text="🎯 Выбрать байера",
                callback_data=f"geo_selectbuyer_{period}{bc}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="period_geo"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def creatives_filters(period: str, breadcrumbs: str = "") -> InlineKeyboardMarkup:
        """Фильтры для отчета по креативам"""
        builder = InlineKeyboardBuilder()
        
        bc = f"_{breadcrumbs}" if breadcrumbs else ""
        
        builder.row(
            InlineKeyboardButton(
                text="🌍 По всем ГЕО",
                callback_data=f"creatives_allgeo_{period}{bc}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🎯 Выбрать ГЕО",
                callback_data=f"creatives_selectgeo_{period}{bc}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="period_creatives"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def offers_filters(period: str, breadcrumbs: str = "") -> InlineKeyboardMarkup:
        """Фильтры для отчета по офферам"""
        builder = InlineKeyboardBuilder()
        
        bc = f"_{breadcrumbs}" if breadcrumbs else ""
        
        builder.row(
            InlineKeyboardButton(
                text="🌍 По всем ГЕО",
                callback_data=f"offers_allgeo_{period}{bc}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🎯 Выбрать ГЕО",
                callback_data=f"offers_selectgeo_{period}{bc}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="period_offers"
            )
        )
        
        return builder.as_markup()
    
    @staticmethod
    def dynamic_selection_list(
        items: List[Dict[str, Any]], 
        callback_prefix: str,
        selected_items: List[str] = None,
        back_callback: str = None,
        max_columns: int = 2
    ) -> InlineKeyboardMarkup:
        """Универсальная клавиатура для выбора элементов из списка"""
        builder = InlineKeyboardBuilder()
        selected = selected_items or []
        
        # Группируем элементы в строки
        for i in range(0, len(items), max_columns):
            row_items = items[i:i + max_columns]
            row_buttons = []
            
            for item in row_items:
                item_id = item.get('id', item.get('name', str(item)))
                text = item.get('display_name', item.get('name', str(item)))
                
                # Добавляем галочку если выбран
                if item_id in selected:
                    text = f"✅ {text}"
                
                row_buttons.append(
                    InlineKeyboardButton(
                        text=text,
                        callback_data=f"{callback_prefix}_{item_id}"
                    )
                )
            
            builder.row(*row_buttons)
        
        # Кнопки управления
        if selected:
            builder.row(
                InlineKeyboardButton(
                    text="✅ Применить выбор",
                    callback_data=f"{callback_prefix}_apply"
                ),
                InlineKeyboardButton(
                    text="🗑 Очистить",
                    callback_data=f"{callback_prefix}_clear"
                )
            )
        
        # Кнопка назад
        if back_callback:
            builder.row(
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=back_callback
                )
            )
        
        return builder.as_markup()
    
    @staticmethod
    def breadcrumbs_navigation(breadcrumbs: List[Dict[str, str]]) -> InlineKeyboardMarkup:
        """Навигационные хлебные крошки"""
        if not breadcrumbs:
            return None
            
        builder = InlineKeyboardBuilder()
        
        # Создаем кнопки для каждого уровня навигации
        for i, crumb in enumerate(breadcrumbs):
            if i == len(breadcrumbs) - 1:
                # Текущий уровень - не кликабельный
                continue
            
            builder.add(
                InlineKeyboardButton(
                    text=crumb['text'],
                    callback_data=crumb['callback']
                )
            )
        
        return builder.as_markup() if len(builder.buttons) > 0 else None
    
    @staticmethod
    def report_actions(report_type: str, filters: Dict[str, Any]) -> InlineKeyboardMarkup:
        """Действия с отчетом (обновить, экспорт, настройки)"""
        builder = InlineKeyboardBuilder()
        
        # Упрощаем callback data чтобы избежать превышения лимита в 64 символа
        # Вместо полного JSON используем только основные параметры
        period = filters.get('period', 'yesterday')
        report_subtype = filters.get('type', 'all')
        
        builder.row(
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=f"refresh_{report_type}_{period}"
            ),
            InlineKeyboardButton(
                text="📊 Детали",
                callback_data=f"details_{report_type}_{report_subtype}"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="⬅️ К фильтрам",
                callback_data=f"filters_{report_type}"
            ),
            InlineKeyboardButton(
                text="🏠 Главная",
                callback_data="reports_main"
            )
        )
        
        return builder.as_markup()