"""
Обработчики для системы отчетов
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.keyboards.reports import ReportsKeyboards
from bot.services.reports import ReportsService
from core.config import settings
from core.enums import ReportPeriod

logger = logging.getLogger(__name__)
router = Router()

# Состояния для FSM
class ReportsStates(StatesGroup):
    main_menu = State()
    traffic_source_selection = State()  # Новое состояние
    period_selection = State()
    filters_selection = State()
    report_display = State()


@router.message(Command("reports"))
async def cmd_reports(message: Message, state: FSMContext):
    """Команда для входа в систему отчетов"""
    user = message.from_user
    
    # Проверка доступа
    allowed_users = settings.allowed_users
    user_info = allowed_users.get(user.id)
    
    if not user_info:
        await message.answer("❌ У вас нет доступа к отчетам.")
        return
    
    await state.set_state(ReportsStates.main_menu)
    
    keyboard = ReportsKeyboards.main_reports_menu()
    
    welcome_text = f"""
📊 <b>Система отчетов</b>

Привет, {user.first_name}! 
Выберите нужный тип отчета:

• <b>Dashboard Сводка</b> - общий обзор по всем метрикам
• <b>Отчет по байерам</b> - детализация по медиабаерам
• <b>Отчет по ГЕО</b> - анализ по странам
• <b>Отчет по креативам</b> - эффективность креативов  
• <b>Отчет по офферам</b> - статистика офферов
"""
    
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")
    logger.info(f"User {user.id} opened reports system")


# ===== ГЛАВНОЕ МЕНЮ ОТЧЕТОВ =====

@router.callback_query(F.data == "reports_main")
async def handle_reports_main(callback: CallbackQuery, state: FSMContext):
    """Возврат к главному меню отчетов"""
    await state.set_state(ReportsStates.main_menu)
    
    keyboard = ReportsKeyboards.main_reports_menu()
    
    text = """
📊 <b>Система отчетов</b>

Выберите нужный тип отчета:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ===== DASHBOARD СВОДКА =====

@router.callback_query(F.data == "reports_dashboard")
async def handle_dashboard_report(callback: CallbackQuery, state: FSMContext):
    """Обработка запроса Dashboard сводки"""
    await state.set_state(ReportsStates.traffic_source_selection)
    await state.update_data(report_type="dashboard")
    
    keyboard = ReportsKeyboards.traffic_source_selection("dashboard")
    
    text = """
📊 <b>Dashboard Сводка</b>

Выберите источник трафика:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ===== ВЫБОР ИСТОЧНИКА ТРАФИКА =====

@router.callback_query(F.data.startswith("trafficsrc_"))
async def handle_traffic_source_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора источника трафика"""
    parts = callback.data.split("_")
    
    if len(parts) == 2:
        # Это возврат к выбору источника трафика (trafficsrc_dashboard)
        report_type = parts[1]
        await state.set_state(ReportsStates.traffic_source_selection)
        
        keyboard = ReportsKeyboards.traffic_source_selection(report_type)
        
        # Получаем название типа отчета для отображения
        report_names = {
            "dashboard": "Dashboard Сводка",
            "buyers": "Отчет по байерам",
            "geo": "Отчет по ГЕО",
            "creatives": "Отчет по креативам",
            "offers": "Отчет по офферам"
        }
        report_display = report_names.get(report_type, report_type)
        
        text = f"""
📊 <b>{report_display}</b>

Выберите источник трафика:
"""
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
        return
    
    if len(parts) < 3:
        await callback.answer("❌ Некорректные данные")
        return
    
    report_type = parts[1]  # dashboard, buyers, geo, etc.
    traffic_source = parts[2]  # google, fb
    
    await state.set_state(ReportsStates.period_selection)
    await state.update_data(report_type=report_type, traffic_source=traffic_source)
    
    # Получаем название источника для отображения
    source_names = {
        "google": "🔍 Google",
        "fb": "📱 FB"
    }
    source_display = source_names.get(traffic_source, traffic_source)
    
    # Получаем название типа отчета для отображения
    report_names = {
        "dashboard": "Dashboard Сводка",
        "buyers": "Отчет по байерам",
        "geo": "Отчет по ГЕО",
        "creatives": "Отчет по креативам",
        "offers": "Отчет по офферам"
    }
    report_display = report_names.get(report_type, report_type)
    
    keyboard = ReportsKeyboards.period_selection(report_type, traffic_source)
    
    text = f"""
📊 <b>{report_display} ({source_display})</b>

Выберите временной период для отчета:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("period_dashboard_"))
async def handle_dashboard_period(callback: CallbackQuery, state: FSMContext):
    """Показ Dashboard с выбранным периодом"""
    # Отладочная информация
    logger.info(f"Dashboard callback data: {callback.data}")
    callback_parts = callback.data.replace("period_dashboard_", "").split("_")
    logger.info(f"Parsed callback parts: {callback_parts}")
    
    # Поддержка как старого формата (без источника), так и нового (с источником)
    if len(callback_parts) >= 2:
        # Новый формат: period_dashboard_google_yesterday или period_dashboard_fb_today
        traffic_source = callback_parts[0]
        period = callback_parts[1]
        
        # Валидация traffic_source
        if traffic_source not in ["google", "fb"]:
            logger.warning(f"Invalid traffic_source: {traffic_source}, falling back to None")
            traffic_source = None
        
        await state.update_data(traffic_source=traffic_source)
        logger.info(f"New format - traffic_source: {traffic_source}, period: {period}")
    else:
        # Старый формат: period_dashboard_yesterday
        period = callback_parts[0]
        traffic_source = None
        logger.info(f"Old format - period: {period}, traffic_source: None")
    
    # Валидация периода
    valid_periods = ["today", "yesterday", "last3days", "last7days", "last15days", "thismonth", "lastmonth"]
    if period not in valid_periods:
        logger.warning(f"Invalid period: {period}, falling back to yesterday")
        period = "yesterday"
    
    await state.set_state(ReportsStates.report_display)
    await state.update_data(report_type="dashboard", period=period)
    
    # Показываем "загрузка"
    await callback.message.edit_text("⏳ Генерируем Dashboard сводку...")
    await callback.answer()
    
    try:
        # Получаем данные с учетом источника трафика
        reports_service = ReportsService()
        user_data = await state.get_data()
        traffic_source = user_data.get("traffic_source")
        
        logger.info(f"Processing dashboard: period={period}, traffic_source={traffic_source}")
        
        dashboard_data = await reports_service.get_dashboard_summary(period, traffic_source)
        
        # Отладочная информация
        logger.info(f"Dashboard data received: {dashboard_data}")
        
        if not dashboard_data:
            await callback.message.edit_text("❌ Не удалось получить данные Dashboard")
            return
        
        totals = dashboard_data.get('totals', {})
        logger.info(f"Totals: clicks={totals.get('clicks', 0)}, leads={totals.get('leads', 0)}")
        
        # Форматируем отчет
        report_text = format_dashboard_report(dashboard_data, period, traffic_source)
        
        # Клавиатура с действиями
        keyboard = ReportsKeyboards.report_actions("dashboard", {"period": period})
        
        await callback.message.edit_text(
            report_text, 
            reply_markup=keyboard, 
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error generating dashboard report: {e}")
        
        # Более информативное сообщение об ошибке
        error_message = "❌ Временная проблема с получением данных\n\n"
        
        if "Broken pipe" in str(e) or "Connection" in str(e):
            error_message += "🔧 Проблема с подключением к серверу Keitaro.\n"
            error_message += "⏱️ Попробуйте через 10-30 секунд.\n\n"
        elif "timeout" in str(e).lower():
            error_message += "⏱️ Превышено время ожидания.\n"
            error_message += "📊 Попробуйте выбрать более короткий период.\n\n"
        else:
            error_message += f"🐛 Техническая ошибка: {str(e)[:100]}\n\n"
        
        error_message += "💡 Что можно сделать:\n"
        error_message += "• Попробуйте другой период\n"
        error_message += "• Подождите 30 секунд\n"
        error_message += "• Обратитесь к администратору"
        
        keyboard = ReportsKeyboards.period_selection("dashboard", None, "reports_main")
        
        await callback.message.edit_text(
            error_message,
            reply_markup=keyboard
        )


# ===== ОТЧЕТЫ ПО БАЙЕРАМ =====

@router.callback_query(F.data == "reports_buyers")
async def handle_buyers_report(callback: CallbackQuery, state: FSMContext):
    """Начало отчета по байерам"""
    await state.set_state(ReportsStates.traffic_source_selection)
    await state.update_data(report_type="buyers")
    
    keyboard = ReportsKeyboards.traffic_source_selection("buyers")
    
    text = """
👥 <b>Отчет по байерам</b>

Выберите источник трафика:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("period_buyers_"))
async def handle_buyers_period(callback: CallbackQuery, state: FSMContext):
    """Выбор фильтров для отчета по байерам"""
    callback_parts = callback.data.replace("period_buyers_", "").split("_")
    
    # Поддержка как старого формата, так и нового с источником трафика
    if len(callback_parts) >= 2:
        # Новый формат: period_buyers_google_yesterday
        traffic_source = callback_parts[0]
        period = callback_parts[1]
        await state.update_data(traffic_source=traffic_source)
    else:
        # Старый формат: period_buyers_yesterday
        period = callback_parts[0]
        traffic_source = None
    
    await state.set_state(ReportsStates.filters_selection)
    await state.update_data(report_type="buyers", period=period)
    
    user_data = await state.get_data()
    traffic_source = user_data.get("traffic_source")
    
    keyboard = ReportsKeyboards.buyers_filters(period, traffic_source)
    
    # Получаем название источника для отображения
    source_names = {
        "google": "🔍 Google",
        "fb": "📱 FB"
    }
    source_display = source_names.get(traffic_source, "") if traffic_source else ""
    title_suffix = f" ({source_display})" if source_display else ""
    
    text = f"""
👥 <b>Отчет по байерам{title_suffix}</b>
📅 Период: {format_period_name(period)}

Выберите тип отчета:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("buyers_all_"))
async def handle_buyers_all_report(callback: CallbackQuery, state: FSMContext):
    """Отчет по всем байерам"""
    parts = callback.data.split("_")
    period = parts[2]
    
    # Получаем источник трафика из состояния FSM
    user_data = await state.get_data()
    traffic_source = user_data.get("traffic_source")
    
    await state.set_state(ReportsStates.report_display)
    await state.update_data(filters={"type": "all", "period": period})
    
    # Показываем источник трафика в сообщении
    traffic_label = ""
    if traffic_source == "google":
        traffic_label = " (Google)"
    elif traffic_source == "fb":
        traffic_label = " (FB)"
    
    await callback.message.edit_text(f"⏳ Генерируем отчет по всем байерам{traffic_label}...")
    await callback.answer()
    
    try:
        reports_service = ReportsService()
        buyers_data = await reports_service.get_buyers_report(period, "all", None, traffic_source)
        
        report_text = format_buyers_report(buyers_data, "all", period, traffic_source)
        keyboard = ReportsKeyboards.report_actions("buyers", {"type": "all", "period": period})
        
        await callback.message.edit_text(
            report_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in buyers report: {e}")
        
        error_message = "❌ Временная проблема с отчетом по байерам\n\n"
        
        if "Broken pipe" in str(e) or "Connection" in str(e):
            error_message += "🔧 Проблема с подключением к Keitaro.\n"
            error_message += "⏱️ Попробуйте через 10-30 секунд."
        else:
            error_message += f"🐛 Ошибка: {str(e)[:100]}"
        
        keyboard = ReportsKeyboards.buyers_filters(period)
        
        await callback.message.edit_text(
            error_message,
            reply_markup=keyboard
        )

@router.callback_query(F.data.startswith("buyers_select_"))
async def handle_buyers_select(callback: CallbackQuery, state: FSMContext):
    """Выбор конкретного байера"""
    period = callback.data.replace("buyers_select_", "")
    
    await state.set_state(ReportsStates.filters_selection)
    await state.update_data(report_type="buyers", period=period, filter_type="select")
    
    await callback.message.edit_text("⏳ Загружаем список байеров...")
    await callback.answer()
    
    try:
        # Получаем список байеров из данных
        reports_service = ReportsService()
        user_data = await state.get_data()
        traffic_source = user_data.get("traffic_source")
        buyers_data = await reports_service.get_buyers_report(period, "all", None, traffic_source)
        
        if not buyers_data:
            await callback.message.edit_text(
                f"❌ Нет данных по байерам за период: {format_period_name(period)}\n\n"
                f"💡 Попробуйте выбрать другой период.",
                reply_markup=ReportsKeyboards.buyers_filters(period)
            )
            return
        
        # Создаем клавиатуру с байерами
        keyboard_buttons = []
        
        # Группируем байеров по 2 в ряд
        for i in range(0, len(buyers_data), 2):
            row = []
            for buyer in buyers_data[i:i+2]:
                buyer_id = buyer.get('buyer_id', 'unknown')
                revenue = buyer.get('revenue', 0)
                leads = buyer.get('leads', 0)
                
                # Форматируем текст кнопки
                button_text = f"👤 {buyer_id} | ${revenue:.0f} | {leads} рег"
                callback_data = f"buyer_{buyer_id}_{period}"
                
                row.append(InlineKeyboardButton(
                    text=button_text,
                    callback_data=callback_data
                ))
            keyboard_buttons.append(row)
        
        # Добавляем кнопку "Назад"
        keyboard_buttons.append([
            InlineKeyboardButton(text="↩️ Назад к фильтрам", callback_data=f"period_buyers_{period}")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        text = f"""
👥 <b>Выбор байера</b>
📅 Период: {format_period_name(period)}

🎯 <b>Выберите байера для детального отчета:</b>

📊 Формат: Байер | Доход | Регистрации
"""
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error loading buyers list: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке списка байеров.\n\n"
            "🔄 Попробуйте еще раз.",
            reply_markup=ReportsKeyboards.buyers_filters(period)
        )

@router.callback_query(F.data.startswith("buyer_") & F.data.contains("_"))
async def handle_individual_buyer_report(callback: CallbackQuery, state: FSMContext):
    """Отчет по конкретному байеру"""
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return
        
    buyer_id = parts[1]
    period = parts[2]
    
    await state.set_state(ReportsStates.report_display)
    await state.update_data(filters={"type": "individual", "buyer_id": buyer_id, "period": period})
    
    await callback.message.edit_text(f"⏳ Генерируем отчет по байеру {buyer_id}...")
    await callback.answer()
    
    try:
        reports_service = ReportsService()
        # Получаем данные по всем байерам и фильтруем нужного
        all_buyers_data = await reports_service.get_buyers_report(period, "all")
        
        # Находим данные конкретного байера
        buyer_data = None
        for buyer in all_buyers_data:
            if buyer.get('buyer_id') == buyer_id:
                buyer_data = buyer
                break
        
        if not buyer_data:
            await callback.message.edit_text(
                f"❌ Нет данных по байеру {buyer_id} за период: {format_period_name(period)}\n\n"
                f"💡 Возможно, у байера не было активности в этот период.",
                reply_markup=ReportsKeyboards.buyers_filters(period)
            )
            return
        
        # Форматируем отчет для одного байера
        text = format_individual_buyer_report(buyer_data, buyer_id, period)
        
        # Клавиатура с действиями
        keyboard_buttons = [
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data=f"buyer_{buyer_id}_{period}"),
                InlineKeyboardButton(text="📊 Другой период", callback_data="reports_buyers")
            ],
            [
                InlineKeyboardButton(text="👥 К списку байеров", callback_data=f"buyers_select_{period}")
            ],
            [
                InlineKeyboardButton(text="📊 Главное меню отчетов", callback_data="reports_main")
            ]
        ]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in individual buyer report: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при генерации отчета по байеру {buyer_id}.\n\n"
            f"🔄 Попробуйте еще раз.",
            reply_markup=ReportsKeyboards.buyers_filters(period)
        )

@router.callback_query(F.data.startswith("buyers_traffic_"))
async def handle_buyers_traffic_report(callback: CallbackQuery, state: FSMContext):
    """Отчет по всему трафику (без группировки по байерам)"""
    period = callback.data.replace("buyers_traffic_", "")
    
    await state.set_state(ReportsStates.report_display)
    await state.update_data(filters={"type": "traffic", "period": period})
    
    await callback.message.edit_text("⏳ Генерируем отчет по всему трафику...")
    await callback.answer()
    
    # Реализация будет добавлена позже
    await callback.message.edit_text(
        "🚧 <b>В разработке</b>\n\n"
        "Отчет по всему трафику будет доступен в следующей версии.",
        reply_markup=ReportsKeyboards.buyers_filters(period),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("buyers_geo_"))
async def handle_buyers_geo_report(callback: CallbackQuery, state: FSMContext):
    """Отчет байеров с разбивкой по ГЕО"""
    period = callback.data.replace("buyers_geo_", "")
    
    await state.set_state(ReportsStates.report_display)
    await state.update_data(filters={"type": "geo", "period": period})
    
    await callback.message.edit_text("⏳ Генерируем отчет по байерам и ГЕО...")
    await callback.answer()
    
    # Реализация будет добавлена позже
    await callback.message.edit_text(
        "🚧 <b>В разработке</b>\n\n"
        "Отчет по байерам с разбивкой по ГЕО будет доступен в следующей версии.",
        reply_markup=ReportsKeyboards.buyers_filters(period),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("buyers_offers_"))
async def handle_buyers_offers_report(callback: CallbackQuery, state: FSMContext):
    """Отчет байеров с разбивкой по офферам"""
    period = callback.data.replace("buyers_offers_", "")
    
    await state.set_state(ReportsStates.report_display)
    await state.update_data(filters={"type": "offers", "period": period})
    
    await callback.message.edit_text("⏳ Генерируем отчет по байерам и офферам...")
    await callback.answer()
    
    # Реализация будет добавлена позже
    await callback.message.edit_text(
        "🚧 <b>В разработке</b>\n\n"
        "Отчет по байерам с разбивкой по офферам будет доступен в следующей версии.",
        reply_markup=ReportsKeyboards.buyers_filters(period),
        parse_mode="HTML"
    )


# ===== ОТЧЕТЫ ПО ГЕО =====

@router.callback_query(F.data == "reports_geo")
async def handle_geo_report(callback: CallbackQuery, state: FSMContext):
    """Начало отчета по ГЕО"""
    await state.set_state(ReportsStates.traffic_source_selection)
    await state.update_data(report_type="geo")
    
    keyboard = ReportsKeyboards.traffic_source_selection("geo")
    
    text = """
🌍 <b>Отчет по ГЕО</b>

Выберите источник трафика:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ===== ОТЧЕТЫ ПО КРЕАТИВАМ =====

@router.callback_query(F.data == "reports_creatives")
async def handle_creatives_report(callback: CallbackQuery, state: FSMContext):
    """Начало отчета по креативам"""
    await state.set_state(ReportsStates.traffic_source_selection)
    await state.update_data(report_type="creatives")
    
    keyboard = ReportsKeyboards.traffic_source_selection("creatives")
    
    text = """
🎨 <b>Отчет по креативам</b>

Выберите источник трафика:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ===== ОТЧЕТЫ ПО ОФФЕРАМ =====

@router.callback_query(F.data == "reports_offers")
async def handle_offers_report(callback: CallbackQuery, state: FSMContext):
    """Начало отчета по офферам"""
    await state.set_state(ReportsStates.traffic_source_selection)
    await state.update_data(report_type="offers")
    
    keyboard = ReportsKeyboards.traffic_source_selection("offers")
    
    text = """
🎯 <b>Отчет по офферам</b>

Выберите источник трафика:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ФОРМАТИРОВАНИЯ =====

def format_period_name(period: str) -> str:
    """Форматирование названия периода"""
    period_names = {
        "today": "Сегодня",
        "yesterday": "Вчера", 
        "last3days": "Последние 3 дня",
        "last7days": "Последние 7 дней",
        "last15days": "Последние 15 дней",
        "thismonth": "Текущий месяц",
        "lastmonth": "Предыдущий месяц"
    }
    return period_names.get(period, period)


def format_dashboard_report(data: Dict[str, Any], period: str, traffic_source: Optional[str] = None) -> str:
    """Форматирование Dashboard отчета"""
    if not data:
        return "❌ Нет данных за выбранный период"
    
    # Основные метрики
    totals = data.get('totals', {})
    top_buyers = data.get('top_buyers', [])[:5]
    top_geos = data.get('top_geos', [])[:5]
    top_creatives = data.get('top_creatives', [])[:5]
    top_offers = data.get('top_offers', [])[:5]
    
    # Добавляем источник трафика в заголовок
    source_names = {
        "google": "🔍 Google",
        "fb": "📱 FB"
    }
    source_display = source_names.get(traffic_source, "") if traffic_source else ""
    title_suffix = f" ({source_display})" if source_display else ""
    
    text = f"""
📊 <b>Dashboard Сводка{title_suffix}</b>
📅 <b>Период:</b> {format_period_name(period)}

💰 <b>Общие показатели:</b>
🖱 Клики (уник): {totals.get('clicks', 0):,}
👤 Регистрации: {totals.get('leads', 0):,}
💳 Депозиты: {totals.get('sales', 0):,}
💰 Доход: ${totals.get('revenue', 0):.2f}

📈 <b>Коэффициенты:</b>
🎯 CR: {totals.get('cr', 0):.2f}%
💎 reg2dep: {format_dep2reg(totals.get('sales', 0), totals.get('leads', 0))}
💰 uEPC: ${totals.get('epc', 0):.3f}
👤 ARPU: ${totals.get('arpu', 0):.2f}
📊 ROI: {totals.get('roi', 0):.1f}%
⚡ Качество трафика: {totals.get('traffic_quality', 0):.1f}%

🏆 <b>Топ-5 байеров по доходу:</b>
"""
    
    for i, buyer in enumerate(top_buyers, 1):
        text += f"{i}. {buyer.get('buyer_id', 'N/A')} - ${buyer.get('revenue', 0):.2f}\n"
    
    text += f"\n🌍 <b>Топ-5 ГЕО по конверсиям:</b>\n"
    for i, geo in enumerate(top_geos, 1):
        text += f"{i}. {geo.get('country', 'N/A')} - {geo.get('conversions', 0)} конв.\n"
    
    text += f"\n🎨 <b>Топ-5 креативов по EPC:</b>\n"
    for i, creative in enumerate(top_creatives, 1):
        creative_id = creative.get('creative_id', 'N/A')
        epc = creative.get('epc', 0)
        text += f"{i}. {creative_id} - ${epc:.3f} EPC\n"
    
    text += f"\n🎯 <b>Топ-5 офферов по объему:</b>\n"
    for i, offer in enumerate(top_offers, 1):
        text += f"{i}. {offer.get('offer_name', 'N/A')} - {offer.get('clicks', 0)} кликов\n"
    
    return text


def format_buyers_report(data: List[Dict[str, Any]], report_type: str, period: str, traffic_source: str = None) -> str:
    """Форматирование отчета по байерам"""
    if not data:
        traffic_label = ""
        if traffic_source == "google":
            traffic_label = " (Google)"
        elif traffic_source == "fb":
            traffic_label = " (FB)"
        return f"❌ Нет данных по байерам за период: {format_period_name(period)}{traffic_label}"
    
    # Добавляем источник трафика в заголовок
    traffic_label = ""
    if traffic_source == "google":
        traffic_label = " (Google)"
    elif traffic_source == "fb":
        traffic_label = " (FB)"
    
    text = f"""
👥 <b>Отчет по байерам{traffic_label}</b>
📅 <b>Период:</b> {format_period_name(period)}
📊 <b>Тип:</b> Все байеры

"""
    
    for buyer in data[:10]:  # Показываем топ-10
        buyer_id = buyer.get('buyer_id', 'N/A')
        clicks = buyer.get('clicks', 0)
        leads = buyer.get('leads', 0)
        sales = buyer.get('sales', 0)
        revenue = buyer.get('revenue', 0)
        cr = buyer.get('cr', 0)
        epc = buyer.get('epc', 0)
        
        text += f"""
<b>{buyer_id}</b>
🖱 {clicks:,} (уник) | 👤 {leads} | 💳 {sales} | ${revenue:.2f}
🎯 CR: {cr:.2f}% | 💎 {format_dep2reg(sales, leads)} | 💰 uEPC: ${epc:.3f}
━━━━━━━━━━━━━━━━━━━━
"""
    
    return text


def format_dep2reg(sales: int, leads: int) -> str:
    """Форматирование показателя dep2reg в формате 1к12 (8.33%)"""
    if not leads or leads == 0:
        return "0к0 (0%)"
    
    if sales == 0:
        return f"0к{leads} (0%)"
    
    ratio = leads / sales
    percentage = (sales / leads) * 100
    
    return f"1к{ratio:.0f} ({percentage:.1f}%)"

def format_individual_buyer_report(buyer_data: Dict[str, Any], buyer_id: str, period: str) -> str:
    """Форматирование отчета для конкретного байера"""
    # Извлекаем данные
    clicks = buyer_data.get('clicks', 0)
    leads = buyer_data.get('leads', 0)
    sales = buyer_data.get('sales', 0)
    revenue = buyer_data.get('revenue', 0)
    cr = buyer_data.get('cr', 0)
    epc = buyer_data.get('epc', 0)
    arpu = buyer_data.get('arpu', 0)
    roi = buyer_data.get('roi', 0)
    costs = buyer_data.get('costs', 0)
    
    text = f"""
👤 <b>Детальный отчет по байеру</b>

🆔 <b>Buyer ID:</b> {buyer_id}
📅 <b>Период:</b> {format_period_name(period)}

📊 <b>Основные показатели:</b>
━━━━━━━━━━━━━━━━━━━━
🖱 <b>Клики (уник):</b> {clicks:,}
👤 <b>Регистрации:</b> {leads}
💳 <b>Депозиты:</b> {sales}
💰 <b>Доход:</b> ${revenue:.2f}
💸 <b>Расходы:</b> ${costs:.2f}
━━━━━━━━━━━━━━━━━━━━

📈 <b>Коэффициенты:</b>
━━━━━━━━━━━━━━━━━━━━
🎯 <b>CR:</b> {cr:.2f}%
💎 <b>reg2dep:</b> {format_dep2reg(sales, leads)}
💰 <b>uEPC:</b> ${epc:.3f}
👤 <b>ARPU:</b> ${arpu:.2f}
📊 <b>ROI:</b> {roi:.1f}%
━━━━━━━━━━━━━━━━━━━━

💡 <b>Анализ эффективности:</b>
"""
    
    # Добавляем анализ эффективности
    if roi > 100:
        text += "✅ Отличная рентабельность (ROI > 100%)\n"
    elif roi > 50:
        text += "⚠️ Средняя рентабельность (ROI 50-100%)\n"
    else:
        text += "❌ Низкая рентабельность (ROI < 50%)\n"
    
    if cr > 5:
        text += "✅ Высокая конверсия в регистрации\n"
    elif cr > 2:
        text += "⚠️ Средняя конверсия в регистрации\n"
    else:
        text += "❌ Низкая конверсия в регистрации\n"
    
    if leads > 0 and sales / leads > 0.1:
        text += "✅ Хорошая конверсия в депозиты\n"
    elif leads > 0 and sales / leads > 0.05:
        text += "⚠️ Средняя конверсия в депозиты\n"
    elif leads > 0:
        text += "❌ Низкая конверсия в депозиты\n"
    
    return text


# ===== ОБНОВЛЕНИЕ ОТЧЕТОВ =====

@router.callback_query(F.data.startswith("refresh_"))
async def handle_refresh_report(callback: CallbackQuery, state: FSMContext):
    """Обновление отчета"""
    parts = callback.data.split("_", 2)
    report_type = parts[1]
    filters_str = parts[2] if len(parts) > 2 else "{}"
    
    try:
        filters = json.loads(filters_str)
    except:
        filters = {}
    
    await callback.message.edit_text("⏳ Обновляем отчет...")
    await callback.answer("🔄 Обновляем данные...")
    
    # Перенаправляем на соответствующий обработчик
    if report_type == "dashboard":
        await handle_dashboard_period(callback, state)
    elif report_type == "buyers":
        await handle_buyers_all_report(callback, state)
    # Добавить остальные типы отчетов


# ===== ВОЗВРАТ К ФИЛЬТРАМ =====

@router.callback_query(F.data.startswith("filters_"))
async def handle_back_to_filters(callback: CallbackQuery, state: FSMContext):
    """Возврат к фильтрам отчета"""
    report_type = callback.data.replace("filters_", "")
    
    user_data = await state.get_data()
    period = user_data.get('period', 'yesterday')
    
    if report_type == "buyers":
        keyboard = ReportsKeyboards.buyers_filters(period)
        text = f"""
👥 <b>Отчет по байерам</b>
📅 Период: {format_period_name(period)}

Выберите тип отчета:
"""
    elif report_type == "geo":
        keyboard = ReportsKeyboards.geo_filters(period)
        text = f"""
🌍 <b>Отчет по ГЕО</b>
📅 Период: {format_period_name(period)}

Выберите фильтры:
"""
    else:
        # Возврат к главному меню если тип не поддерживается
        await handle_reports_main(callback, state)
        return
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ===== ГЛАВНОЕ МЕНЮ =====

@router.callback_query(F.data == "main_menu")
async def handle_main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат к главному меню бота"""
    await state.clear()
    
    text = """
🏠 <b>Главное меню</b>

Выберите нужное действие:
"""
    
    # Здесь можно добавить клавиатуру главного меню бота
    # keyboard = MainMenuKeyboards.main_menu()
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()