import unittest
from io import BytesIO

from openpyxl import Workbook

from flowguard.importers import records_from_csv, records_from_json, records_from_xlsx


class ImporterTests(unittest.TestCase):
    def test_russian_csv_columns_are_mapped(self):
        result = records_from_csv(
            "Клиент,Номер телефона,Сумма,Комментарий\n"
            "Иван,+7 999 111-22-33,5000,перенести на вечер\n"
        )
        self.assertEqual(result.records[0]["client_name"], "Иван")
        self.assertEqual(result.records[0]["phone"], "+7 999 111-22-33")
        self.assertEqual(result.records[0]["amount"], "5000")
        self.assertEqual(result.source_format, "csv")

    def test_excel_first_sheet_is_imported(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Заявки"
        sheet.append(["Клиент", "Телефон", "Статус"])
        sheet.append(["Анна", "89991112233", "new"])
        buffer = BytesIO()
        workbook.save(buffer)

        result = records_from_xlsx(buffer.getvalue())
        self.assertEqual(result.sheet_name, "Заявки")
        self.assertEqual(result.records[0]["client_name"], "Анна")

    def test_json_aliases_are_mapped(self):
        result = records_from_json([{"name": "Alex", "email": "a@example.test"}])
        self.assertEqual(result.records[0]["client_name"], "Alex")

    def test_unknown_columns_fail_with_clear_message(self):
        with self.assertRaisesRegex(ValueError, "Не удалось распознать"):
            records_from_csv("Колонка один,Колонка два\n1,2\n")


if __name__ == "__main__":
    unittest.main()
