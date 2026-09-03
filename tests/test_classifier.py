import unittest

from flowguard.classifier import IntentClassifier


class IntentClassifierTests(unittest.TestCase):
    def setUp(self):
        self.classifier = IntentClassifier()

    def test_evaluation_is_above_release_gate(self):
        self.assertGreaterEqual(self.classifier.evaluate()["accuracy"], 0.70)

    def test_russian_reschedule_note(self):
        prediction = self.classifier.predict("клиент хочет перенести запись на вечер")
        self.assertEqual(prediction.label, "reschedule")
        self.assertGreater(prediction.confidence, 0.25)

    def test_empty_note_is_neutral(self):
        prediction = self.classifier.predict("")
        self.assertEqual(prediction.label, "neutral")
        self.assertEqual(prediction.confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
