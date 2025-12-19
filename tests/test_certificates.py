
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bot import get_payment_details, send_certificate_thanks, notify_admin_certificate

# ============================================================================
# 1. Тесты формирования данных для платежа
# ============================================================================

def test_get_payment_details_kid():
    """Проверка описания для сертификата Kid"""
    desc = get_payment_details(product_id='kid', product_name='Cert Kid', phone='+79990000000')
    assert "подарит ребёнку ЭКОамулет" in desc
    assert "бесплатном эко-уроке" in desc

def test_get_payment_details_special():
    """Проверка описания для сертификата Special"""
    desc = get_payment_details(product_id='special', product_name='Cert Special', phone='+79990000000')
    assert "подарит ЭКОамулет человеку с особенностями" in desc
    assert "инклюзивной мастерской" in desc

def test_get_payment_details_amulet():
    """Проверка стандартного описания для амулета"""
    desc = get_payment_details(product_id='amulet', product_name='ЭКОамулет', phone='+79990000000')
    assert "Заказ ЭКОамулет для +79990000000" == desc

# ============================================================================
# 2. Тесты уведомлений (Mock)
# ============================================================================

@pytest.mark.asyncio
async def test_send_certificate_thanks_success():
    """Проверка отправки благодарности для kid/special"""
    with patch('bot.application') as mock_app:
        mock_app.bot.send_message = AsyncMock(return_value=True)
        
        # Тест для kid
        result = await send_certificate_thanks(user_id=123, product_id='kid')
        assert result is True
        mock_app.bot.send_message.assert_called()
        
        # Тест для amulet (не должно отправляться)
        mock_app.bot.send_message.reset_mock()
        result_amulet = await send_certificate_thanks(user_id=123, product_id='amulet')
        assert result_amulet is False
        mock_app.bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_notify_admin_certificate():
    """Проверка отправки админ-уведомления"""
    with patch('bot.application') as mock_app:
        mock_app.bot.send_message = AsyncMock(return_value=True)
        
        order_data = {
            'product_id': 'kid',
            'product_price': 1000,
            'user_id': 12345,
            'phone': '+79998887766'
        }
        
        await notify_admin_certificate(order_data, payment_id='pay_123')
        
        # Проверяем, что вызов был
        mock_app.bot.send_message.assert_called_once()
        
        # Проверяем текст сообщения
        args, kwargs = mock_app.bot.send_message.call_args
        assert "🎁 **НОВЫЙ СЕРТИФИКАТ!**" in kwargs['text']
        assert "1000 ₽" in kwargs['text']

# ============================================================================
# 3. Интеграционный тест записи в Sheets (Mock Sheets)
# ============================================================================

from bot import add_order_to_sheets_with_retry

@pytest.mark.asyncio
async def test_add_order_to_sheets_params():
    """Проверяем, что в Sheets передаются правильные параметры товара"""
    with patch('bot.sheets', new_callable=MagicMock) as mock_sheets:
        mock_sheets.add_order.return_value = True
        
        await add_order_to_sheets_with_retry(
            payment_id='pay_test',
            user_id=111,
            fio='Ivanov',
            address='Moscow',
            phone='+7000',
            product_name='Super Cert',
            product_price=5000
        )
        
        mock_sheets.add_order.assert_called_with(
            payment_id='pay_test',
            user_id=111,
            fio='Ivanov',
            address='Moscow',
            phone='+7000',
            product='Super Cert',  # Важно: должно быть передано имя товара
            price=5000,            # Важно: должна быть передана цена
            status='Ожидание оплаты'
        )
