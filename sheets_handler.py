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

    def get_products_raw(self) -> List[Dict]:
        """
        Internal: Get all products from 'Остатки' sheet with row numbers.
        Returns list of dicts: [{'id': '...', 'name': '...', 'price': ..., 'stock': ..., 'row': ...}, ...]
        """
        try:
            worksheet = self.sheet.worksheet(self.SHEET_STOCK)
            all_values = worksheet.get_all_values()
            
            products = []
            
            # Skip header if present (heuristic: checks if first row has "product_id" or "id")
            start_index = 0
            if all_values and len(all_values) > 0:
                first_cell = str(all_values[0][0]).lower().strip()
                if 'id' in first_cell or 'product' in first_cell:
                    start_index = 1

            for i in range(start_index, len(all_values)):
                row_data = all_values[i]
                # Expecting at least 4 columns: ID, Name, Price, Stock
                if len(row_data) < 4:
                    continue
                
                p_id = str(row_data[0]).strip()
                if not p_id: 
                    continue
                    
                try:
                    price = int(str(row_data[2]).replace(' ', '').replace(',', '').split('.')[0])
                except:
                    price = 0
                    
                try:
                    stock = int(str(row_data[3]).replace(' ', '').split('.')[0])
                except:
                    stock = 0

                products.append({
                    'id': p_id,
                    'name': str(row_data[1]).strip(),
                    'price': price,
                    'stock': stock,
                    'row': i + 1  # 1-based index for gspread usage
                })
                
            return products
        except Exception as e:
            logger.error(f"❌ Error reading products: {e}")
            return []

    def get_products(self) -> Dict[str, Dict]:
        """
        Public: Get products as a dictionary keyed by product_id.
        Ex: {'amulet': {'name': '...', 'price': 1900, 'stock': 100}, ...}
        """
        raw = self.get_products_raw()
        result = {}
        for p in raw:
            # removing 'id' and 'row' from the value dict to match user spec examples strictly,
            # or keeping them? User example: "amulet": {"name": "...", "price": 1900, "stock": 100}
            result[p['id']] = {
                'name': p['name'],
                'price': p['price'],
                'stock': p['stock']
            }
        return result

    def get_stock(self) -> int:
        """
        Get stock for the main product 'amulet'.
        Backward compatibility for existing code.
        """
        try:
            products = self.get_products()
            # Default ID is 'amulet' as per plan
            item = products.get('amulet')
            if item:
                return item['stock']
            
            # Fallback/Empty check
            logger.warning("⚠️ Main product 'amulet' not found in stock sheet.")
            return 0
        except Exception as e:
            logger.error(f"❌ Ошибка получения остатка: {e}")
            raise e

    def set_stock(self, quantity: int) -> bool:
        """
        Set stock quantity for main product 'amulet'.
        Backward compatibility.
        """
        try:
            # We need the row number. Re-read raw products to find it.
            # This is slightly inefficient (read all to write one), but safe and simple.
            # Optimization: could use worksheet.find('amulet', in_column=1) if available,
            # but getting all values is robust against structure variations if we use the same parsing logic.
            
            vals = self.get_products_raw()
            target_row = None
            for p in vals:
                if p['id'] == 'amulet':
                    target_row = p['row']
                    break
            
            if target_row:
                worksheet = self.sheet.worksheet(self.SHEET_STOCK)
                # Stock is column D (4)
                worksheet.update_cell(target_row, 4, quantity)
                return True
            else:
                logger.error("❌ Cannot update stock: Product 'amulet' not found.")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка обновления остатка: {e}")
            return False

    def add_order(self, payment_id: str, user_id: int, fio: str, 
                 address: str, phone: str, product: str, price: int, status: str, ref_code: str = None) -> bool:
        """Add new order to 'Заказы' sheet"""
        try:
            worksheet = self.sheet.worksheet(self.SHEET_ORDERS)
            
            # Columns: Payment ID, FIO, Address, Phone, Product, Price, Status, Date
            row = [
                payment_id,
                fio,
                address,
                phone,
                product,
                price,
                status,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
            
            # Find the next available row in Column A
            # col_values(1) returns all values in the first column
            next_row = len(worksheet.col_values(1)) + 1
            
            # Explicitly define the range A{row}:H{row} to force correct placement
            # Columns: A, B, C, D, E, F, G, H (8 columns)
            target_range = f"A{next_row}:H{next_row}"
            
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
            
            # Columns: Phone, User ID, Date
            row = [
                phone,
                user_id,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
            
            # Find the next available row in Column A
            next_row = len(worksheet.col_values(1)) + 1
            
            # Explicitly define the range A{row}:C{row}
            # Columns: A, B, C (3 columns)
            target_range = f"A{next_row}:C{next_row}"
            
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
            all_values = worksheet.get_all_values()
            
            result = []
            
            # Check if first row is header
            start_index = 0
            if all_values and len(all_values) > 0:
                first_row = all_values[0]
                # Simple heuristic: check if first cell looks like a header "Phone" or "Телефон"
                if str(first_row[0]).lower() in ['phone', 'телефон', 'номер']:
                   start_index = 1

            for i in range(start_index, len(all_values)):
                row = all_values[i]
                
                # Ensure row has enough columns (at least Phone and User ID)
                if len(row) < 2:
                    continue
                    
                phone = str(row[0]).strip()
                potential_uid = str(row[1]).strip()
                
                # Check if the second column is actually a User ID (digits)
                # If it's a date (e.g. 2025-12-02), it won't be digits.
                if potential_uid.isdigit():
                    user_id = potential_uid
                    date = str(row[2]).strip() if len(row) > 2 else ""
                else:
                    # Fallback for old format [Phone, Date] or invalid data
                    # We cannot notify this user without an ID, so we skip
                    # logger.warning(f"⚠️ Skipped row with invalid User ID: {row}")
                    continue

                if phone and user_id:
                     # Clean up phone (optional)
                    result.append({
                        'phone': phone,
                        'user_id': user_id,
                        'date': date
                    })
            
            return result
            
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения листа ожидания: {e}")
            return []

    def clear_waitlist(self) -> bool:
        """Clear all data from 'Ожидание' sheet"""
        try:
            worksheet = self.sheet.worksheet(self.SHEET_WAITLIST)
            worksheet.clear()
            logger.info("🧹 Лист ожидания успешно очищен")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка очистки листа ожидания: {e}")
            return False
