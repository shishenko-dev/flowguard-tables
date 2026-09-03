import unittest

from flowguard.analyzer import analyze_records, normalize_phone


class AnalyzerTests(unittest.TestCase):
    def test_phone_normalisation_unifies_russian_formats(self):
        self.assertEqual(normalize_phone("8 (999) 111-22-33"), "79991112233")
        self.assertEqual(normalize_phone("+7 999 111 22 33"), "79991112233")

    def test_duplicates_and_status_conflict_are_explained(self):
        records = [
            {
                "id": "A",
                "client_name": "Test Client",
                "phone": "+7 999 111-22-33",
                "scheduled_at": "2026-09-04T10:00:00+03:00",
                "status": "confirmed",
                "amount": "5000",
                "notes": "client confirmed the appointment",
            },
            {
                "id": "B",
                "client_name": "Test Client",
                "phone": "8 999 111 22 33",
                "scheduled_at": "2026-09-04T10:00:00+03:00",
                "status": "pending",
                "amount": "5000",
                "notes": "please cancel the booking",
            },
        ]
        analysis = analyze_records(records)
        self.assertEqual(analysis["summary"]["duplicate_groups"], 1)
        second = next(row for row in analysis["records"] if row["id"] == "B")
        self.assertIn("duplicate", second["flags"])
        self.assertIn("status_note_conflict", second["flags"])

    def test_large_amount_is_detected_as_outlier(self):
        records = [
            {"id": str(index), "client_name": f"Client {index}", "phone": f"+7999000000{index}", "amount": amount}
            for index, amount in enumerate([4900, 5000, 5100, 5200, 125000])
        ]
        analysis = analyze_records(records)
        flagged = [row for row in analysis["records"] if "amount_outlier" in row["flags"]]
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]["id"], "4")

    def test_cancelled_record_with_amount_requires_attention(self):
        analysis = analyze_records(
            [
                {
                    "id": "CANCELLED-1",
                    "client_name": "Test Client",
                    "phone": "+79990000000",
                    "status": "cancelled",
                    "amount": "5000",
                    "notes": "please cancel my booking",
                }
            ]
        )
        record = analysis["records"][0]
        self.assertEqual(record["priority"], "attention")
        self.assertEqual(record["recommended_action"], "Check today")

    def test_run_limit_is_enforced(self):
        with self.assertRaises(ValueError):
            analyze_records({"id": str(index)} for index in range(5001))


if __name__ == "__main__":
    unittest.main()
