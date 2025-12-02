import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from typing import List, Dict, Optional
import os

logger = logging.getLogger(__name__)

class GoogleSheetsHandler:
    """
    Handler for Google Sheets interaction using gspread.
    """
    def __init__(self):
        self.scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        self.creds_file = 'creds.json'
        self.client = None
        self.sheet = None
        
        # Sheet names
        self.SHEET_STOCK = "Остатки"
        self.SHEET_ORDERS = "Заказы"
        self.SHEET_WAITLIST = "Ожидание"
        
        self._connect()

    def _connect(self):
        """Connect to Google Sheets"""
        try:
            if not os.path.exists(self.creds_file):
                raise FileNotFoundError(f"Файл {self.creds_file} не найден!")
                
            self.creds = ServiceAccountCredentials.from_json_keyfile_name(self.creds_file, self.scope)
            self.client = gspread.authorize(self.creds)
            
            # Open the spreadsheet (assuming it's shared with the service account)
            # You might need to specify the sheet name if it's different
            sheet_id = os.getenv('GOOGLE_SHEET_ID')
            if sheet_id:
                self.sheet = self.client.open_by_key(sheet_id)
            else:
                # Fallback: try to open by name if ID is not set, or raise error
                # For now, let's assume we need the ID from .env as per bot.py
                raise ValueError("GOOGLE_SHEET_ID не установлен в .env")
                
            logger.info("✅ Успешное подключение к Google Sheets")
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Google Sheets: {e}")
            raise e

    def get_stock(self) -> int:
        """Get current stock quantity from 'Остатки' sheet (Cell B2)"""
        try:
            worksheet = self.sheet.worksheet(self.SHEET_STOCK)
            # Assuming stock is in cell B2
            val = worksheet.acell('B2').value
            return int(val) if val else 0
        except Exception as e:
            logger.error(f"❌ Ошибка получения остатка: {e}")
            # Re-raise or return 0? bot.py handles exceptions, so re-raise to trigger retry/local fallback
            raise e

    def set_stock(self, quantity: int) -> bool:
        """Set stock quantity in 'Остатки' sheet (Cell B2)"""
        try:
            worksheet = self.sheet.worksheet(self.SHEET_STOCK)
            worksheet.update('B2', quantity)
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обновления остатка: {e}")
            return False

    def add_order(self, payment_id: str, user_id: int, fio: str, 
                 address: str, phone: str, product: str, price: int, status: str, ref_code: str = None) -> bool:
        """Add new order to 'Заказы' sheet"""
        try:
            worksheet = self.sheet.worksheet(self.SHEET_ORDERS)
            
            # Columns: Payment ID, FIO, Address, Phone, Product, Price, Status, Ref Code, Date
            row = [
                payment_id,
                fio,
                address,
                phone,
                product,
                price,
                status,
                ref_code if ref_code else "",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
            
            # Find the next available row in Column A
            # col_values(1) returns all values in the first column
            next_row = len(worksheet.col_values(1)) + 1
            
            # Explicitly define the range A{row}:I{row} to force correct placement
            # Columns: A, B, C, D, E, F, G, H, I (9 columns)
            target_range = f"A{next_row}:I{next_row}"
            
            logger.info(f"📝 Writing order to {target_range}")
            
            # Update the specific range
            worksheet.update(target_range, [row])
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления заказа: {e}")
            return False

    def update_order_status(self, payment_id: str, new_status: str) -> bool:
        """Update order status in 'Заказы' sheet"""
        try:
            worksheet = self.sheet.worksheet(self.SHEET_ORDERS)
            
            # Find the cell with payment_id
            cell = worksheet.find(payment_id)
            if cell:
                # Assuming Status is in column 7 (G)
                # PaymentID (A) -> 1, Status (G) -> 7
                # But we should be careful if columns change. 
                # Let's assume fixed structure for now as per plan.
                worksheet.update_cell(cell.row, 7, new_status)
                return True
            else:
                logger.warning(f"⚠️ Заказ {payment_id} не найден в таблице")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса заказа: {e}")
            return False

    def add_to_waitlist(self, phone: str, user_id: int) -> bool:
        """Add user to 'Ожидание' sheet"""
        try:
            worksheet = self.sheet.worksheet(self.SHEET_WAITLIST)
            
            # Columns: Phone, Date
            row = [
                phone,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
            
            # Find the next available row in Column A
            next_row = len(worksheet.col_values(1)) + 1
            
            # Explicitly define the range A{row}:B{row}
            # Columns: A, B (2 columns)
            target_range = f"A{next_row}:B{next_row}"
            
            logger.info(f"📝 Writing waitlist entry to {target_range}")
            
            worksheet.update(target_range, [row])
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления в лист ожидания: {e}")
            return False

    def get_waitlist(self) -> List[Dict]:
        """Get all users from 'Ожидание' sheet"""
        try:
            worksheet = self.sheet.worksheet(self.SHEET_WAITLIST)
            all_values = worksheet.get_all_records()
            
            # Expected format from get_all_records is list of dicts with headers as keys
            # We need to map it to what bot.py expects
            # bot.py expects: {'phone': ..., 'user_id': ..., 'date': ...}
            
            # If headers are: Phone, User ID, Date
            # keys will be 'Phone', 'User ID', 'Date'
            
            # Let's handle potential header case sensitivity or naming
            # For robustness, let's just return what we get and let bot.py handle it?
            # No, bot.py expects specific keys.
            
            result = []
            for row in all_values:
                # Try to find keys
                phone = row.get('Phone') or row.get('phone') or row.get('Телефон')
                uid = row.get('User ID') or row.get('user_id') or row.get('ID')
                date = row.get('Date') or row.get('date') or row.get('Дата')
                
                if phone and uid:
                    result.append({
                        'phone': str(phone),
                        'user_id': str(uid),
                        'date': str(date)
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения листа ожидания: {e}")
            return []
