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
logger.setLevel(logging.DEBUG)

# Log module loading
logger.info("="*60)
logger.info("REPORTS MODULE LOADED")
logger.info("="*60)

router = Router()

# Log router creation
logger.info("Reports router created and ready for registration")

# Состояния для FSM
class ReportsStates(StatesGroup):
    main_menu = State()
    traffic_source_selection = State()  # Новое состояние
    period_selection = State()
    filters_selection = State()
    report_display = State()
    export_type_selection = State()
    export_period_selection = State()
    export_processing = State()


@router.message(Command("reports"))
async def cmd_reports(message: Message, state: FSMContext):
    """Команда для входа в систему отчетов"""
    logger.warning(f"====== /REPORTS HANDLER TRIGGERED ======")
    logger.warning(f"User ID: {message.from_user.id}")
    logger.warning(f"Username: {message.from_user.username}")
    logger.warning(f"Message text: '{message.text}'")
    logger.warning(f"Chat ID: {message.chat.id}")
    
    user = message.from_user
    
    # Проверка доступа
    allowed_users = settings.allowed_users
    logger.info(f"Getting allowed users from settings...")
    logger.info(f"Allowed users keys: {list(allowed_users.keys())}")
    
    user_info = allowed_users.get(user.id) or allowed_users.get(str(user.id))
    
    logger.info(f"Reports access check for user {user.id}: user_info={user_info}")
    
    if not user_info:
        logger.warning(f"Access denied for user {user.id}")
        await message.answer("❌ У вас нет доступа к отчетам.")
        return
    
    logger.info(f"Access granted for user {user.id}, role: {user_info.get('role', 'unknown')}")
    
    await state.set_state(ReportsStates.main_menu)
    
    keyboard = ReportsKeyboards.main_reports_menu()
    logger.info("Reports menu keyboard created")
    
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
    logger.warning(f"====== /REPORTS HANDLER COMPLETED SUCCESSFULLY ======")


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
        
        # Добавляем кнопку "Назад" с сохранением источника трафика
        user_data = await state.get_data()
        if user_data.get('traffic_source'):
            back_callback = f"period_buyers_{user_data['traffic_source']}_{period}"
        else:
            back_callback = f"period_buyers_{period}"
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="↩️ Назад к фильтрам", callback_data=back_callback)
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


# Добавленные команды

@router.message(Command("stats_creo"))
async def cmd_stats_creo(message: Message):
    """Статистика по конкретному креативу"""
    from bot.services.creatives import CreativesService
    
    # Проверяем, указан ли ID креатива в команде
    command_parts = message.text.split()
    
    if len(command_parts) == 1:
        # ID не указан, показываем инструкцию
        await message.answer(
            "📊 <b>Статистика креативов</b>\n\n"
            "Отправьте ID креатива для получения статистики:\n"
            "<code>/stats_creo IDAZ090825001</code>\n\n"
            "Формат ID: IDGEOДДММГГNNN\n"
            "• ID - префикс\n"
            "• GEO - страна (AZ, TR, US, и т.д.)\n"
            "• ДДММГГ - дата\n"
            "• NNN - номер",
            parse_mode="HTML"
        )
        return
    
    creative_id = command_parts[1].upper()
    
    # Ищем креатив в базе данных
    creative = await CreativesService.get_creative_by_id(creative_id)
    
    if not creative:
        await message.answer(
            f"❌ <b>Креатив не найден</b>\n\n"
            f"Креатив с ID <code>{creative_id}</code> не найден в базе данных.\n\n"
            f"Проверьте правильность написания ID или используйте /my_creos для просмотра ваших креативов.",
            parse_mode="HTML"
        )
        return
    
    # Показываем информацию о креативе
    response = f"📊 <b>Статистика креатива</b>\n\n"
    response += CreativesService.format_creative_info(creative)
    response += "\n🚧 <b>Статистика по кликам/конверсиям</b>\n"
    response += "Интеграция со статистикой Keitaro будет добавлена в следующей версии."
    
    await message.answer(response, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("stats_geo_offer"))
async def cmd_stats_geo_offer(message: Message):
    """Статистика по GEO и офферам"""
    await message.answer(
        "🌍 <b>Статистика GEO/офферов</b>\n\n"
        "🚧 Функция в разработке\n\n"
        "Будет доступна статистика по:\n"
        "• Географическим регионам\n"
        "• Офферам и их конверсии\n"
        "• Доходности по странам",
        parse_mode="HTML"
    )


@router.message(Command("my_creos"))
async def cmd_my_creos(message: Message):
    """Мои загруженные креативы"""
    from bot.services.creatives import CreativesService
    
    user_id = message.from_user.id
    
    # Получаем креативы пользователя
    creatives = await CreativesService.get_user_creatives(user_id, limit=10)
    total_count = await CreativesService.count_user_creatives(user_id)
    
    if not creatives:
        await message.answer(
            "🎨 <b>Мои креативы</b>\n\n"
            "📭 У вас пока нет загруженных креативов.\n\n"
            "Используйте /upload для загрузки первого креатива!",
            parse_mode="HTML"
        )
        return
    
    # Формируем ответ
    response = f"🎨 <b>Мои креативы</b> (показано {len(creatives)} из {total_count})\n\n"
    
    for creative in creatives:
        response += CreativesService.format_creative_info(creative)
        response += "━━━━━━━━━━━━━━━━━━━━\n"
    
    if total_count > 10:
        response += f"\n📄 Показаны последние 10 креативов из {total_count} всего"
    
    await message.answer(response, parse_mode="HTML", disable_web_page_preview=True)


@router.message(lambda message: message.text and message.text.startswith("/get_"))
async def handle_get_creative(message: Message):
    """Получение файла креатива по ID"""
    from bot.services.creatives import CreativesService
    from integrations.telegram.storage import TelegramStorageService
    
    # Извлекаем creative_id из команды
    creative_id = message.text.replace("/get_", "").upper()
    
    # Получаем креатив из БД
    creative = await CreativesService.get_creative_by_id(creative_id)
    
    if not creative:
        await message.answer(
            f"❌ Креатив с ID <code>{creative_id}</code> не найден.\n\n"
            f"Проверьте правильность ID или используйте /my_creos для просмотра ваших креативов.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем доступ (креатив принадлежит пользователю или пользователь имеет права)
    user_id = message.from_user.id
    if creative.uploader.tg_user_id != user_id:
        # Здесь можно добавить проверку прав доступа для админов/менеджеров
        await message.answer(
            "❌ У вас нет доступа к этому креативу.",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, что у креатива есть Telegram file_id
    if not creative.telegram_file_id or creative.telegram_file_id.startswith('temp_'):
        await message.answer(
            f"❌ Файл креатива недоступен.\n\n"
            f"Этот креатив был загружен до перехода на Telegram хранилище.",
            parse_mode="HTML"
        )
        return
    
    # Отправляем файл пользователю
    try:
        caption = f"""🎨 <b>{creative.creative_id}</b>
🌍 GEO: {creative.geo}
📝 Файл: {creative.original_name or 'Неизвестно'}
📊 Размер: {round(creative.size_bytes / (1024 * 1024), 1) if creative.size_bytes else 0} MB
📅 Загружен: {creative.upload_dt.strftime("%d.%m.%Y %H:%M") if creative.upload_dt else 'Неизвестно'}"""
        
        if creative.notes:
            caption += f"\n💬 Описание: {creative.notes}"
        
        # Отправляем файл используя telegram_file_id
        await message.answer_document(
            document=creative.telegram_file_id,
            caption=caption,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error sending creative file: {e}")
        await message.answer(
            "❌ Ошибка при отправке файла.\n\n"
            "Попробуйте еще раз позже.",
            parse_mode="HTML"
        )


@router.message(Command("stats_buyer"))
async def cmd_stats_buyer(message: Message):
    """Статистика по байерам"""
    await message.answer(
        "👥 <b>Статистика байеров</b>\n\n"
        "Используйте /reports для доступа к полной системе отчетов по байерам.\n\n"
        "Доступные отчеты:\n"
        "• Отчет по всем байерам\n"
        "• Фильтрация по источникам трафика\n"
        "• Детальная статистика по периодам",
        parse_mode="HTML"
    )


@router.message(Command("export"))
async def cmd_export(message: Message, state: FSMContext):
    """Экспорт отчетов в Google Таблицы"""
    await state.set_state(ReportsStates.export_type_selection)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Креативы", callback_data="export_creatives")],
        [InlineKeyboardButton(text="👥 Байеры", callback_data="export_buyers")],
        [InlineKeyboardButton(text="🌍 ГЕО", callback_data="export_geo")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="reports_cancel")]
    ])
    
    text = """
📊 <b>Экспорт в Google Таблицы</b>

🎯 <b>Выберите тип отчета для экспорта:</b>

📊 <b>Креативы</b> - статистика по креативам с анализом успешности
👥 <b>Байеры</b> - отчет по медиабаерам с метриками эффективности  
🌍 <b>ГЕО</b> - анализ по географическим регионам

💡 <b>Отчет будет создан в Google Таблицах со ссылкой для доступа</b>
"""
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# ===== ОТЧЕТЫ ПО КРЕАТИВАМ (продолжение) =====

@router.callback_query(F.data.startswith("period_creatives_"))
async def handle_creatives_period_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора периода для отчета по креативам"""
    logger.info(f"=== CALLBACK PARSING DEBUG ===")
    logger.info(f"Raw callback data: {callback.data}")
    
    parts = callback.data.split("_")
    logger.info(f"Split parts: {parts}")
    
    # Извлекаем период и источник трафика
    # Формат: period_creatives_fb_yesterday или period_creatives_yesterday
    if len(parts) >= 4:
        # Новый формат: period_creatives_traffic_source_period
        traffic_source = parts[2]
        period = parts[3]
        logger.info(f"4+ parts format: traffic_source={traffic_source}, period={period}")
        
        # Валидация traffic_source
        if traffic_source not in ["google", "fb"]:
            logger.warning(f"Invalid traffic_source in creatives: {traffic_source}, falling back to None")
            traffic_source = None
            period = parts[2]  # Если источник неверный, используем как период
            logger.info(f"After validation: traffic_source={traffic_source}, period={period}")
    elif len(parts) >= 3:
        # Старый формат: period_creatives_period
        period = parts[2]
        traffic_source = None
        logger.info(f"3 parts format: traffic_source=None, period={period}")
    else:
        logger.error(f"Invalid callback format: {callback.data}")
        await callback.answer("❌ Некорректные данные")
        return
    
    # Валидация периода
    valid_periods = ["today", "yesterday", "last3days", "last7days", "last15days", "thismonth", "lastmonth"]
    if period not in valid_periods:
        logger.warning(f"Invalid period in creatives: {period}, falling back to yesterday")
        period = "yesterday"
    
    logger.info(f"Final parsed values: traffic_source={traffic_source}, period={period}")
    
    await state.set_state(ReportsStates.filters_selection)
    await state.update_data(
        report_type="creatives", 
        period=period, 
        traffic_source=traffic_source
    )
    
    # CRITICAL DEBUG: Verify period was saved
    debug_data = await state.get_data()
    logger.info(f"PERIOD SAVE CHECK - Data after update: {debug_data}")
    logger.info(f"PERIOD SAVE CHECK - Period value: {debug_data.get('period', 'MISSING!')}")
    
    # Создаем клавиатуру для выбора байера
    keyboard_buttons = []
    
    # Кнопка "По всем байерам"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="📊 По всем байерам",
            callback_data=f"creo_buyer_all_{period}"
        )
    ])
    
    # Кнопка "Выбрать байера"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="👤 Выбрать байера",
            callback_data=f"creo_buyer_select_{period}"
        )
    ])
    
    # Кнопка назад
    if traffic_source:
        back_callback = f"trafficsrc_creatives_{traffic_source}"
    else:
        back_callback = "trafficsrc_creatives"
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="↩️ Назад", callback_data=back_callback)
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    text = f"""
🎨 <b>Отчет по креативам</b>
📅 Период: {format_period_name(period)}

Выберите фильтр по байерам:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("creo_buyer_"))
async def handle_creatives_buyer_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора байера для отчета по креативам"""
    parts = callback.data.split("_")
    
    if len(parts) < 3:
        await callback.answer("❌ Некорректные данные")
        return
    
    action = parts[2]  # all или select
    
    # ИСПРАВЛЕНИЕ: Получаем период из callback, т.к. FSM state сбрасывается
    if len(parts) >= 4:
        period = parts[3]  # Период из callback
        logger.info(f"Period from callback: {period}")
    else:
        # Fallback: пытаемся найти период в callback data
        callback_str = callback.data
        period_match = None
        valid_periods = ["today", "yesterday", "last3days", "last7days", "last15days", "thismonth", "lastmonth"]
        for p in valid_periods:
            if p in callback_str:
                period_match = p
                break
        period = period_match or "yesterday"
        logger.info(f"Period extracted from callback string: {period}")
    
    logger.info(f"creo_buyer handler: action={action}, period={period}, callback={callback.data}")
    
    # Сохраняем период в state для последующих использований
    await state.update_data(period=period)
    
    if action == "select":
        # Показываем список байеров для выбора
        await callback.message.edit_text("⏳ Загружаем список байеров...")
        
        try:
            reports_service = ReportsService()
            user_data = await state.get_data()
            traffic_source = user_data.get("traffic_source")
            
            # Получаем список байеров
            buyers_data = await reports_service.get_buyers_report(period, "all", None, traffic_source)
            
            if not buyers_data:
                # Получаем traffic_source для правильного callback
                user_data = await state.get_data()
                traffic_source = user_data.get("traffic_source")
                if traffic_source:
                    back_callback = f"period_creatives_{traffic_source}_{period}"
                else:
                    back_callback = f"period_creatives_{period}"
                    
                await callback.message.edit_text(
                    f"❌ Нет данных по байерам за период: {format_period_name(period)}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="↩️ Назад", callback_data=back_callback)
                    ]])
                )
                return
            
            # Создаем клавиатуру с байерами
            keyboard_buttons = []
            
            for i in range(0, len(buyers_data), 2):
                row = []
                for buyer in buyers_data[i:i+2]:
                    buyer_id = buyer.get('buyer_id', 'unknown')
                    row.append(InlineKeyboardButton(
                        text=f"👤 {buyer_id}",
                        callback_data=f"creo_setbuyer_{buyer_id}_{period}"
                    ))
                keyboard_buttons.append(row)
            
            keyboard_buttons.append([
                InlineKeyboardButton(text="↩️ Назад", callback_data=f"period_creatives_{period}")
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback.message.edit_text(
                f"👥 <b>Выберите байера</b>\n📅 Период: {format_period_name(period)}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"Error loading buyers for creatives: {e}")
            await callback.message.edit_text("❌ Ошибка при загрузке списка байеров")
    
    else:
        # all - переходим к выбору гео
        await state.update_data(buyer_id="all")
        await show_creatives_geo_selection(callback, state, period)


@router.callback_query(F.data.startswith("creo_setbuyer_"))
async def handle_creatives_set_buyer(callback: CallbackQuery, state: FSMContext):
    """Установка выбранного байера и переход к выбору гео"""
    parts = callback.data.split("_")
    
    if len(parts) < 4:
        await callback.answer("❌ Некорректные данные")
        return
    
    buyer_id = parts[2]
    # Получаем реальный период из state, а не из callback
    user_data = await state.get_data()
    period = user_data.get("period", "yesterday")
    
    logger.info(f"creo_setbuyer handler: buyer_id={buyer_id}, period_from_state={period}, callback={callback.data}")
    
    await state.update_data(buyer_id=buyer_id)
    await show_creatives_geo_selection(callback, state, period)


async def show_creatives_geo_selection(callback: CallbackQuery, state: FSMContext, period: str):
    """Показать выбор гео для отчета по креативам"""
    user_data = await state.get_data()
    buyer_id = user_data.get("buyer_id", "all")
    
    # Создаем клавиатуру для выбора гео
    keyboard_buttons = []
    
    # Кнопка "Все гео"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="🌍 Все гео",
            callback_data=f"creo_geo_all_{period}"
        )
    ])
    
    # Кнопка "Выбрать гео"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="📍 Выбрать гео",
            callback_data=f"creo_geo_select_{period}"
        )
    ])
    
    # Кнопка назад
    keyboard_buttons.append([
        InlineKeyboardButton(text="↩️ Назад", callback_data=f"period_creatives_{period}")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    text = f"""
🎨 <b>Отчет по креативам</b>
📅 Период: {format_period_name(period)}
👤 Байер: {buyer_id}

Выберите фильтр по гео:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("creo_geo_"))
async def handle_creatives_geo_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора гео для отчета по креативам"""
    parts = callback.data.split("_")
    
    if len(parts) < 4:
        await callback.answer("❌ Некорректные данные")
        return
    
    action = parts[2]  # all или select
    # ИСПРАВЛЕНИЕ: Получаем период из callback или state
    if len(parts) >= 4:
        period = parts[3]  # Период из callback
        logger.info(f"Period from callback: {period}")
    else:
        # Fallback: пытаемся получить из state (если был сохранен ранее)
        user_data = await state.get_data()
        period = user_data.get("period", "yesterday")
        logger.info(f"Period from state fallback: {period}")
    
    logger.info(f"creo_geo handler: action={action}, period={period}, callback={callback.data}")
    
    # Убеждаемся что период сохранен в state
    await state.update_data(period=period)
    
    if action == "select":
        # Показываем список гео для выбора
        # Список популярных гео
        geos = ["AT", "AZ", "BE", "BG", "CH", "CZ", "DE", "ES", "FR", "HR", 
                "HU", "IT", "NL", "PL", "RO", "SI", "SK", "TR", "UK", "US"]
        
        keyboard_buttons = []
        
        # Группируем гео по 4 в ряд
        for i in range(0, len(geos), 4):
            row = []
            for geo in geos[i:i+4]:
                row.append(InlineKeyboardButton(
                    text=f"🌍 {geo}",
                    callback_data=f"creo_setgeo_{geo}_{period}"
                ))
            keyboard_buttons.append(row)
        
        # Кнопка назад
        user_data = await state.get_data()
        buyer_id = user_data.get("buyer_id", "all")
        if buyer_id == "all":
            back_callback = f"creo_buyer_all_{period}"
        else:
            back_callback = f"creo_setbuyer_{buyer_id}_{period}"
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="↩️ Назад", callback_data=back_callback)
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(
            f"🌍 <b>Выберите гео</b>\n📅 Период: {format_period_name(period)}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    else:
        # all - переходим к выбору метрики сортировки
        await state.update_data(geo="all")
        await show_creatives_metric_selection(callback, state, period)


@router.callback_query(F.data.startswith("creo_setgeo_"))
async def handle_creatives_set_geo(callback: CallbackQuery, state: FSMContext):
    """Установка выбранного гео и переход к выбору метрики"""
    parts = callback.data.split("_")
    
    if len(parts) < 4:
        await callback.answer("❌ Некорректные данные")
        return
    
    geo = parts[2]
    # Получаем реальный период из state, а не из callback
    user_data = await state.get_data()
    period = user_data.get("period", "yesterday")
    
    logger.info(f"creo_setgeo handler: geo={geo}, period_from_state={period}, callback={callback.data}")
    
    await state.update_data(geo=geo)
    await show_creatives_metric_selection(callback, state, period)


async def show_creatives_metric_selection(callback: CallbackQuery, state: FSMContext, period: str):
    """Показать выбор метрики для сортировки креативов"""
    user_data = await state.get_data()
    buyer_id = user_data.get("buyer_id", "all")
    geo = user_data.get("geo", "all")
    
    # Создаем клавиатуру для выбора метрики
    keyboard_buttons = []
    
    # Кнопки выбора метрики
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="💰 Лучшие по uEPC",
            callback_data=f"creo_show_uepc_{period}"
        )
    ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="💵 Лучшие по доходу",
            callback_data=f"creo_show_revenue_{period}"
        )
    ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="📅 Лучшие по сроку жизни",
            callback_data=f"creo_show_active_{period}"
        )
    ])
    
    # Кнопка назад
    if geo == "all":
        back_callback = f"creo_geo_all_{period}"
    else:
        back_callback = f"creo_setgeo_{geo}_{period}"
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="↩️ Назад", callback_data=back_callback)
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    text = f"""
🎨 <b>Отчет по креативам</b>
📅 Период: {format_period_name(period)}
👤 Байер: {buyer_id}
🌍 Гео: {geo}

Выберите метрику для сортировки:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("creo_show_"))
async def handle_creatives_show_report(callback: CallbackQuery, state: FSMContext):
    """Показать отчет по креативам"""
    parts = callback.data.split("_")
    
    if len(parts) < 3:
        await callback.answer("❌ Некорректные данные")
        return
    
    metric = parts[2]  # uepc, revenue, active
    
    # ИСПРАВЛЕНИЕ: Получаем период из callback
    if len(parts) >= 4:
        period = parts[3]  # Период из callback
        logger.info(f"Period from callback: {period}")
    else:
        # Fallback: пытаемся найти период в callback data или state
        callback_str = callback.data
        period_match = None
        valid_periods = ["today", "yesterday", "last3days", "last7days", "last15days", "thismonth", "lastmonth"]
        for p in valid_periods:
            if p in callback_str:
                period_match = p
                break
        
        if period_match:
            period = period_match
            logger.info(f"Period extracted from callback string: {period}")
        else:
            # Последний fallback - из state
            user_data = await state.get_data()
            period = user_data.get("period", "yesterday")
            logger.info(f"Period from state fallback: {period}")
    
    logger.info(f"creo_show handler: metric={metric}, period={period}, callback={callback.data}")
    
    # Сохраняем метрику для возможности пересортировки
    await state.update_data(current_metric=metric)
    
    # Показываем отчет
    await show_creatives_report(callback, state, period, metric)


async def show_creatives_report(callback: CallbackQuery, state: FSMContext, period: str, sort_by: str):
    """Отобразить отчет по креативам"""
    await callback.message.edit_text("⏳ Генерируем отчет по креативам...")
    await callback.answer()
    
    try:
        user_data = await state.get_data()
        buyer_id = user_data.get("buyer_id", "all")
        geo = user_data.get("geo", "all")
        traffic_source = user_data.get("traffic_source")
        
        # Детальное логирование
        logger.info(f"=== CREATIVES REPORT DEBUG ===")
        logger.info(f"Callback data: {callback.data}")
        logger.info(f"Period from callback: {period}")
        logger.info(f"Sort by: {sort_by}")
        logger.info(f"User data: {user_data}")
        logger.info(f"Final parameters: period={period}, buyer_id={buyer_id}, geo={geo}, traffic_source={traffic_source}")
        
        # Получаем данные
        reports_service = ReportsService()
        creatives_data = await reports_service.get_creatives_report(
            period=period,
            buyer_id=buyer_id if buyer_id != "all" else None,
            geo=geo if geo != "all" else None,
            traffic_source=traffic_source,
            sort_by=sort_by
        )
        
        logger.info(f"Received {len(creatives_data)} creatives from service")
        # Log TR36 if found
        tr36 = next((c for c in creatives_data if c['creative_id'] == 'TR36'), None)
        if tr36:
            logger.info(f"TR36 found: revenue=${tr36['revenue']}, unique_clicks={tr36['unique_clicks']}, sort_metric={tr36.get(sort_by, 'N/A')}")
        else:
            logger.info(f"TR36 not found in {len(creatives_data)} creatives")
            # Log first 5 creative IDs for debugging
            creative_ids = [c['creative_id'] for c in creatives_data[:5]]
            logger.info(f"First 5 creative IDs: {creative_ids}")
        
        if not creatives_data:
            # Используем правильный формат callback для кнопки Назад
            user_data = await state.get_data()
            traffic_source = user_data.get("traffic_source")
            if traffic_source:
                back_callback = f"period_creatives_{traffic_source}_{period}"
            else:
                back_callback = f"period_creatives_{period}"
                
            await callback.message.edit_text(
                f"❌ Нет данных по креативам за выбранный период",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="↩️ Назад", callback_data=back_callback)
                ]])
            )
            return
        
        # Форматируем отчет
        metric_names = {
            "uepc": "uEPC",
            "revenue": "доходу",
            "active": "сроку жизни"
        }
        
        text = f"""
🎨 <b>Топ-5 креативов по {metric_names.get(sort_by, sort_by)}</b>
📅 Период: {format_period_name(period)}
👤 Байер: {buyer_id}
🌍 Гео: {geo}

"""
        
        for i, creative in enumerate(creatives_data, 1):
            text += f"""
{i}. <b>ID: {creative['creative_id']}</b>
👤 Байер: {creative['buyer_id']}
🌍 Гео: {creative['geos']}
🖱 Уник. клики: {creative['unique_clicks']:,}
📝 Регистрации: {creative['leads']:,}
💳 Депозиты: {creative['deposits']:,}
💰 Доход: ${creative['revenue']:,.2f}
📊 Деп/Рег: {creative['dep_to_reg']:.1f}%
💵 uEPC: ${creative['uepc']:.2f}
📅 Активных дней: {creative['active_days']}

"""
        
        # Кнопки для пересортировки
        keyboard_buttons = []
        
        # Показываем другие варианты сортировки
        if sort_by != "uepc":
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="💰 Пересортировать по uEPC",
                    callback_data=f"creo_resort_uepc_{period}"
                )
            ])
        
        if sort_by != "revenue":
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="💵 Пересортировать по доходу",
                    callback_data=f"creo_resort_revenue_{period}"
                )
            ])
        
        if sort_by != "active":
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="📅 Пересортировать по сроку жизни",
                    callback_data=f"creo_resort_active_{period}"
                )
            ])
        
        # Кнопка назад (используем правильный формат с traffic_source)
        user_data = await state.get_data()
        traffic_source = user_data.get("traffic_source")
        if traffic_source:
            back_callback = f"period_creatives_{traffic_source}_{period}"
        else:
            back_callback = f"period_creatives_{period}"
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="↩️ Изменить фильтры", callback_data=back_callback)
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error generating creatives report: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при генерации отчета",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="↩️ Назад", callback_data=back_callback)
            ]])
        )


@router.callback_query(F.data.startswith("creo_resort_"))
async def handle_creatives_resort(callback: CallbackQuery, state: FSMContext):
    """Пересортировка отчета по креативам"""
    parts = callback.data.split("_")
    
    if len(parts) < 4:
        await callback.answer("❌ Некорректные данные")
        return
    
    metric = parts[2]  # uepc, revenue, active
    # Получаем реальный период из state, а не из callback
    user_data = await state.get_data()
    period = user_data.get("period", "yesterday")
    
    logger.info(f"creo_resort handler: metric={metric}, period_from_state={period}, callback={callback.data}")
    
    # Показываем отчет с новой сортировкой
    await show_creatives_report(callback, state, period, metric)


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


# ===== ЭКСПОРТ В GOOGLE SHEETS =====

@router.message(Command("export"))
async def cmd_export(message: Message, state: FSMContext):
    """Экспорт отчетов в Google Таблицы"""
    user = message.from_user
    
    # Проверка доступа
    allowed_users = settings.allowed_users
    user_info = allowed_users.get(user.id) or allowed_users.get(str(user.id))
    
    if not user_info:
        await message.answer("❌ У вас нет доступа к экспорту отчетов.")
        return
    
    await state.set_state(ReportsStates.export_type_selection)
    
    keyboard_buttons = [
        [InlineKeyboardButton(text="🎨 Креативы", callback_data="export_creatives")],
        [InlineKeyboardButton(text="👥 Байеры", callback_data="export_buyers")],
        [InlineKeyboardButton(text="🌍 ГЕО", callback_data="export_geo")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    text = """
📊 <b>Экспорт отчетов в Google Таблицы</b>

Выберите тип отчета для экспорта:
"""
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.in_(["export_creatives", "export_buyers", "export_geo"]))
async def handle_export_type(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа экспорта"""
    export_type = callback.data.replace("export_", "")
    logger.info(f"Export type selected: {export_type} by user {callback.from_user.id}")
    
    try:
        await state.update_data(export_type=export_type)
        await state.set_state(ReportsStates.export_period_selection)
    except Exception as e:
        logger.error(f"❌ ERROR updating state: {e}")
        await callback.answer(f"❌ Ошибка при обновлении состояния: {e}")
        return
    
    # Клавиатура с периодами
    keyboard_buttons = [
        [
            InlineKeyboardButton(text="📅 Сегодня", callback_data="export_period_today"),
            InlineKeyboardButton(text="📅 Вчера", callback_data="export_period_yesterday")
        ],
        [
            InlineKeyboardButton(text="📅 Последние 3 дня", callback_data="export_period_last3days"),
            InlineKeyboardButton(text="📅 Последние 7 дней", callback_data="export_period_last7days")
        ],
        [
            InlineKeyboardButton(text="📅 Этот месяц", callback_data="export_period_thismonth"),
            InlineKeyboardButton(text="📅 Прошлый месяц", callback_data="export_period_lastmonth")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="export_back_to_types")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    export_names = {
        "creatives": "Креативы",
        "buyers": "Байеры", 
        "geo": "ГЕО"
    }
    
    text = f"""
📊 <b>Экспорт: {export_names.get(export_type, export_type)}</b>

Выберите период для экспорта:
"""
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        # Ignore "message is not modified" errors when user clicks same button twice
        if "message is not modified" not in str(e).lower():
            logger.warning(f"Failed to edit message: {e}")
    
    await callback.answer()


@router.callback_query(F.data.startswith("export_period_"))
async def handle_export_period(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора периода для экспорта"""
    period = callback.data.replace("export_period_", "")
    logger.info(f"Export period selected: {period} by user {callback.from_user.id}")
    
    try:
        user_data = await state.get_data()
        export_type = user_data.get("export_type")
        
        if not export_type:
            logger.error("❌ NO EXPORT TYPE IN STATE DATA!")
            await callback.answer("❌ Ошибка: тип экспорта не определен. Попробуйте начать заново.")
            return
        
        await state.set_state(ReportsStates.export_processing)
        logger.info(f"Starting export: type={export_type}, period={period}")
        
    except Exception as e:
        logger.error(f"❌ ERROR IN EXPORT PERIOD HANDLER SETUP: {e}")
        await callback.answer(f"❌ Ошибка при обработке: {e}")
        return
    
    period_names = {
        "today": "Сегодня",
        "yesterday": "Вчера", 
        "last3days": "Последние 3 дня",
        "last7days": "Последние 7 дней",
        "thismonth": "Этот месяц",
        "lastmonth": "Прошлый месяц"
    }
    
    logger.critical("🔄 Attempting to edit message...")
    try:
        await callback.message.edit_text(
            f"⏳ Экспортируем отчет по {export_type} за {period_names.get(period, period)}...\n\n"
            f"📝 Создаем Google Таблицу...",
            parse_mode="HTML"
        )
        logger.critical("✅ Message edited successfully")
    except Exception as e:
        logger.error(f"❌ Failed to edit message: {e}")
    
    try:
        await callback.answer()
        logger.critical("✅ Callback answered")
    except Exception as e:
        logger.error(f"❌ Failed to answer callback: {e}")
    
    try:
        logger.critical("📦 Importing GoogleSheetsReportsExporter...")
        from integrations.google.reports_export import GoogleSheetsReportsExporter
        logger.critical("✅ Import successful")
        
        logger.critical("🏗️ Creating exporter instance...")
        exporter = GoogleSheetsReportsExporter()
        logger.critical("✅ Exporter created")
        
        logger.critical(f"🚀 Starting export for type: {export_type}, period: {period}")
        
        # Выполняем экспорт в зависимости от типа
        if export_type == "creatives":
            logger.critical("📊 Calling export_creatives_report...")
            spreadsheet_url = await exporter.export_creatives_report(period)
        elif export_type == "buyers":
            logger.critical("👥 Calling export_buyers_report...")
            spreadsheet_url = await exporter.export_buyers_report(period)
        elif export_type == "geo":
            logger.critical("🌍 Calling export_geo_report...")
            spreadsheet_url = await exporter.export_geo_report(period)
        else:
            logger.error(f"❌ Unsupported export type: {export_type}")
            raise ValueError(f"Неподдерживаемый тип экспорта: {export_type}")
        
        logger.critical(f"✅ Export completed successfully! URL: {spreadsheet_url}")
        
        # Успешный экспорт
        success_text = f"""
✅ <b>Экспорт завершен успешно!</b>

📊 <b>Тип:</b> {export_type}
📅 <b>Период:</b> {period_names.get(period, period)}
🔗 <b>Ссылка:</b> <a href="{spreadsheet_url}">Открыть таблицу</a>

💡 Таблица была создана в Google Drive и готова к использованию.
"""
        
        keyboard_buttons = [
            [InlineKeyboardButton(text="🔄 Новый экспорт", callback_data="export_new")],
            [InlineKeyboardButton(text="📊 К отчетам", callback_data="reports_main")]
        ]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        try:
            await callback.message.edit_text(
                success_text,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception as e:
            # Ignore "message is not modified" errors
            if "message is not modified" not in str(e).lower():
                logger.warning(f"Failed to edit success message: {e}")
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        
        error_text = f"""
❌ <b>Ошибка при экспорте</b>

📊 <b>Тип:</b> {export_type}
📅 <b>Период:</b> {period_names.get(period, period)}
🐛 <b>Ошибка:</b> {str(e)[:200]}

🔄 Попробуйте еще раз или выберите другой период.
"""
        
        keyboard_buttons = [
            [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"export_period_{period}")],
            [InlineKeyboardButton(text="↩️ К выбору периода", callback_data="export_back_to_period")],
            [InlineKeyboardButton(text="📊 К отчетам", callback_data="reports_main")]
        ]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        try:
            await callback.message.edit_text(
                error_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            # Ignore "message is not modified" errors
            if "message is not modified" not in str(e).lower():
                logger.warning(f"Failed to edit error message: {e}")


@router.callback_query(F.data == "export_new")
async def handle_export_new(callback: CallbackQuery, state: FSMContext):
    """Начать новый экспорт"""
    await cmd_export(callback.message, state)


@router.callback_query(F.data == "export_back_to_types")  
async def handle_export_back_to_types(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору типа экспорта"""
    await state.set_state(ReportsStates.export_type_selection)
    
    keyboard_buttons = [
        [InlineKeyboardButton(text="🎨 Креативы", callback_data="export_creatives")],
        [InlineKeyboardButton(text="👥 Байеры", callback_data="export_buyers")],
        [InlineKeyboardButton(text="🌍 ГЕО", callback_data="export_geo")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    text = """
📊 <b>Экспорт отчетов в Google Таблицы</b>

Выберите тип отчета для экспорта:
"""
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        # Ignore "message is not modified" errors when user clicks same button twice
        if "message is not modified" not in str(e).lower():
            logger.warning(f"Failed to edit message: {e}")
    await callback.answer()


@router.callback_query(F.data == "export_back_to_period")
async def handle_export_back_to_period(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору периода экспорта"""
    user_data = await state.get_data()
    export_type = user_data.get("export_type", "creatives")
    
    await state.set_state(ReportsStates.export_period_selection)
    
    # Клавиатура с периодами  
    keyboard_buttons = [
        [
            InlineKeyboardButton(text="📅 Сегодня", callback_data="export_period_today"),
            InlineKeyboardButton(text="📅 Вчера", callback_data="export_period_yesterday")
        ],
        [
            InlineKeyboardButton(text="📅 Последние 3 дня", callback_data="export_period_last3days"),
            InlineKeyboardButton(text="📅 Последние 7 дней", callback_data="export_period_last7days")
        ],
        [
            InlineKeyboardButton(text="📅 Этот месяц", callback_data="export_period_thismonth"),
            InlineKeyboardButton(text="📅 Прошлый месяц", callback_data="export_period_lastmonth")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="export_back_to_types")]
    ]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    export_names = {
        "creatives": "Креативы",
        "buyers": "Байеры",
        "geo": "ГЕО"
    }
    
    text = f"""
📊 <b>Экспорт: {export_names.get(export_type, export_type)}</b>

Выберите период для экспорта:
"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()