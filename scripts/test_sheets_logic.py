import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path to import sheets_handler
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sheets_handler import GoogleSheetsHandler

class TestGoogleSheetsHandler(unittest.TestCase):
    def setUp(self):
        # Patch the connection so we don't need real creds
        self.patcher = patch('sheets_handler.ServiceAccountCredentials')
        self.MockCreds = self.patcher.start()
        
        self.patcher_gspread = patch('sheets_handler.gspread')
        self.MockGspread = self.patcher_gspread.start()
        
        # Patch os.path.exists to simulate creds file existence
        self.patcher_exists = patch('os.path.exists', return_value=True)
        self.MockExists = self.patcher_exists.start()

         # Patch os.getenv to return a dummy sheet ID
        self.patcher_getenv = patch('os.getenv', return_value='dummy_sheet_id')
        self.MockGetenv = self.patcher_getenv.start()
        
        self.handler = GoogleSheetsHandler()
        
        # Mock the sheet and worksheet
        self.mock_sheet = MagicMock()
        self.mock_worksheet = MagicMock()
        self.handler.client.open_by_key.return_value = self.mock_sheet
        self.handler.sheet = self.mock_sheet
        self.mock_sheet.worksheet.return_value = self.mock_worksheet

    def tearDown(self):
        self.patcher.stop()
        self.patcher_gspread.stop()
        self.patcher_exists.stop()
        self.patcher_getenv.stop()

    def test_get_products(self):
        # Setup mock data for "Остатки"
        # Columns: ID, Name, Price, Stock
        # Row 1 is header
        # Row 2 is amulet
        # Row 3 is kid
        # Row 4 is bad data
        self.mock_worksheet.get_all_values.return_value = [
            ['product_id', 'name', 'price', 'stock'],
            ['amulet', 'ЭКОамулет', '1 900', '100'],
            ['kid', 'Сертификат', '1000', '9999'],
            ['', 'Empty ID', '0', '0'],
            ['garbage']
        ]

        products = self.handler.get_products()
        
        print(f"Parsed products: {products}")

        self.assertIn('amulet', products)
        self.assertEqual(products['amulet']['stock'], 100)
        self.assertEqual(products['amulet']['price'], 1900)
        
        self.assertIn('kid', products)
        self.assertEqual(products['kid']['stock'], 9999)
        
        self.assertNotIn('', products)

    def test_get_stock_legacy(self):
        # Setup mock data
        self.mock_worksheet.get_all_values.return_value = [
            ['id', 'name', 'price', 'stock'],
            ['amulet', 'Main Product', '100', '50']
        ]
        
        stock = self.handler.get_stock()
        self.assertEqual(stock, 50)
        
        # Test fallback
        self.mock_worksheet.get_all_values.return_value = [['id', '...'], ['other', '...', '1', '1']]
        stock_empty = self.handler.get_stock()
        self.assertEqual(stock_empty, 0)

    def test_set_stock_legacy(self):
        # Setup mock data to find row for 'amulet'
        # 'amulet' is at index 1 -> row 2
        self.mock_worksheet.get_all_values.return_value = [
            ['id', 'name', 'price', 'stock'],
            ['amulet', 'Main Product', '100', '50']
        ]
        
        result = self.handler.set_stock(99)
        
        self.assertTrue(result)
        # Should call update_cell(2, 4, 99) because 'amulet' is at row 2, and stock is col 4
        self.mock_worksheet.update_cell.assert_called_with(2, 4, 99)

if __name__ == '__main__':
    unittest.main()
