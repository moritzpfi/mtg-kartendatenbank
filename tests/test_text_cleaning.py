"""Checks of observed source defects and preservation of valid card data."""

from copy import deepcopy
import unittest

from scripts.text_cleaning import add_audit, audit_summary, clean_card


class TextCleaningTests(unittest.TestCase):
    def test_observed_defects_and_original_preservation(self):
        original = {"id": "a", "name": "Minsc & Boo", "originalText": "It costs {1}\u200b less.\n{T}",
                    "foreignNames": [{"name": "Vortici d\u0090'Etere", "text": "Vol\n\u0081À chaque fois &amp; Buh"}],
                    "rulings": [{"text": "  Keep <sad trombone noises>. "}, {"text": ""}],
                    "future": {"enabled": False, "value": None, "number": 0, "items": ["Ä", "飛行"]}}
        before = deepcopy(original)
        cleaned, changes, warnings = clean_card(original)
        self.assertEqual(original, before)
        self.assertEqual(cleaned["foreignNames"], [{"name": "Vortici d'Etere", "text": "Vol\nÀ chaque fois & Buh"}])
        self.assertEqual(cleaned["originalText"], "It costs {1} less.\n{T}")
        self.assertEqual(cleaned["rulings"], [{"text": "Keep <sad trombone noises>."}, {"text": ""}])
        self.assertEqual(cleaned["future"], original["future"])
        self.assertEqual(sum(event["operations"] for event in changes if event["rule"] == "edge_spaces"), 3)
        self.assertFalse(warnings)
        self.assertEqual(clean_card(original), clean_card(original))
        self.assertEqual(clean_card(cleaned)[0], cleaned)
        self.assertFalse(clean_card(cleaned)[1])

    def test_valid_symbols_and_unknown_fields_are_untouched(self):
        card = {"id": " a ", "name": "Name", "originalText": "{U}\n飛行 — é\u00a0: \u200d",
                "foreignNames": [{"text": "{T}\nCréature\u00a0: エルフ <Token.Name=Faction>"}],
                "rulings": [{"text": "\n keep inner  spaces\n"}],
                "imageUrl": "https://example.invalid/?a=&amp;b=2", "unknown": "\u0081 &amp;\u200b"}
        cleaned, changes, warnings = clean_card(card)
        self.assertEqual(cleaned, card)
        self.assertFalse(changes)
        self.assertFalse(warnings)

    def test_multiple_and_unknown_entities_are_reported_without_further_decoding(self):
        for value in ("Minsc &amp;amp; Boo", "&amp;#38;", "&lt;literal&gt;", "&unknown;"):
            with self.subTest(value=value):
                card = {"foreignNames": [{"text": value}]}
                cleaned, changes, warnings = clean_card(card)
                self.assertEqual(cleaned, card)
                self.assertFalse(changes)
                self.assertTrue(warnings)
                self.assertEqual(clean_card(cleaned)[0], cleaned)

    def test_missing_and_nonstring_optional_fields_are_preserved(self):
        for card in ({}, {"foreignNames": None}, {"rulings": [{"text": None}, 0]},
                     {"originalText": False, "foreignNames": [{"text": 0}, {"name": None}]}):
            self.assertEqual(clean_card(card), (card, [], []))

    def test_audit_counts_texts_and_distinct_cards_separately(self):
        metrics, warnings, examples = {}, {}, {}
        card = {"id": "a", "foreignNames": [{"text": "\u0081 &amp;"}, {"text": "&amp;"}]}
        add_audit(card, metrics, warnings, examples)
        report = audit_summary(metrics, warnings, examples, 2)
        self.assertEqual(report["changed_cards"], 1)
        self.assertEqual(report["percent_of_raw_cards"], 50)
        entity = next(group for group in report["groups"] if group["rule"] == "amp_entity")
        self.assertEqual((entity["changed_values"], entity["operations"], entity["cards"]), (2, 2, 1))


if __name__ == "__main__":
    unittest.main()
