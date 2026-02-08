"""Tests for JSON extraction and validation logic."""
import unittest

from src.negotiation.parser import extract_json, validate_action_json


class TestExtractJSON(unittest.TestCase):

    def test_clean_json(self):
        text = (
            '{"action": "offer", "offer_price": 50.0, '
            '"message_public": "hi", "rationale_private": "r"}'
        )
        result = extract_json(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "offer")
        self.assertEqual(result["offer_price"], 50.0)

    def test_markdown_fenced(self):
        text = (
            '```json\n{"action": "counter", "offer_price": 60, '
            '"message_public": "no", "rationale_private": "r"}\n```'
        )
        result = extract_json(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "counter")

    def test_extra_text_around(self):
        text = (
            'Here is my answer:\n'
            '{"action": "accept", "offer_price": null, '
            '"message_public": "ok", "rationale_private": "good"}\n'
            'Hope that helps!'
        )
        result = extract_json(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "accept")

    def test_pure_garbage(self):
        self.assertIsNone(extract_json("This is not JSON at all"))

    def test_empty_string(self):
        self.assertIsNone(extract_json(""))

    def test_repair_single_quotes(self):
        text = (
            "{'action': 'offer', 'offer_price': 42, "
            "'message_public': 'hi', 'rationale_private': 'r'}"
        )
        result = extract_json(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["offer_price"], 42)

    def test_repair_trailing_comma(self):
        text = (
            '{"action": "reject", "offer_price": null, '
            '"message_public": "no", "rationale_private": "done",}'
        )
        result = extract_json(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "reject")


class TestValidateActionJSON(unittest.TestCase):

    def _valid_offer(self, **overrides):
        obj = {
            "action": "offer",
            "offer_price": 50,
            "message_public": "hi",
            "rationale_private": "r",
        }
        obj.update(overrides)
        return obj

    def test_valid_offer(self):
        ok, reason = validate_action_json(self._valid_offer())
        self.assertTrue(ok, reason)

    def test_valid_accept(self):
        ok, _ = validate_action_json(self._valid_offer(action="accept", offer_price=None))
        self.assertTrue(ok)

    def test_missing_field(self):
        obj = {"action": "offer", "offer_price": 50}
        ok, reason = validate_action_json(obj)
        self.assertFalse(ok)
        self.assertIn("Missing", reason)

    def test_invalid_action(self):
        ok, reason = validate_action_json(self._valid_offer(action="bid"))
        self.assertFalse(ok)
        self.assertIn("Invalid action", reason)

    def test_offer_without_price(self):
        ok, reason = validate_action_json(self._valid_offer(offer_price=None))
        self.assertFalse(ok)

    def test_negative_price(self):
        ok, reason = validate_action_json(self._valid_offer(offer_price=-10))
        self.assertFalse(ok)

    def test_accept_auto_corrects_price(self):
        obj = self._valid_offer(action="accept", offer_price=99)
        ok, _ = validate_action_json(obj)
        self.assertTrue(ok)
        self.assertIsNone(obj["offer_price"])


if __name__ == "__main__":
    unittest.main()
