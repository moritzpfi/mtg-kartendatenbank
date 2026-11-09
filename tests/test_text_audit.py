"""Regression checks for text defects observed in the actual API snapshot."""

import unittest

from scripts.audit_text import flags, strings


class TextAuditTests(unittest.TestCase):
    def test_c1_controls_in_translation_are_detected(self):
        self.assertTrue(flags("Vol\n\u0081À chaque fois")["unexpected_control"])
        self.assertTrue(flags("Vortici d\u0090'Etere")["unexpected_control"])

    def test_mtg_content_and_multilingual_text_are_preserved(self):
        for value in ("{U}: Flying\n{T}: Add {G}.", "Fliegend — Créature", "飛行"):
            with self.subTest(value=value):
                findings = flags(value)
                self.assertFalse(findings["unexpected_control"])
                self.assertFalse(findings["possible_mojibake"])
                self.assertFalse(findings["html_entity"])

    def test_encoded_entities_and_invisible_characters_are_separate(self):
        self.assertTrue(flags("Minsc &amp; Boo")["html_entity"])
        self.assertFalse(flags("Minsc & Boo")["html_entity"])
        self.assertTrue(flags("{1}\u200b less")["format_character"])
        self.assertTrue(flags("Créature\u00a0: elfe")["nonbreaking_space"])

    def test_angle_brackets_are_only_a_review_signal(self):
        self.assertTrue(flags("<sad trombone noises>")["html_tag"])
        self.assertTrue(flags("<Token.Name=Faction>")["html_tag"])
        self.assertFalse(flags("Power < 3")["html_tag"])

    def test_nested_strings_use_stable_field_paths(self):
        value = {"name": "A", "foreignNames": [{"text": "B"}, {"text": "C"}], "cmc": 0, "extra": None}
        self.assertEqual(list(strings(value)), [("name", "A"), ("foreignNames[].text", "B"), ("foreignNames[].text", "C")])


if __name__ == "__main__":
    unittest.main()
