import unittest

from src.evaluation import check_chunk_hit
from src.ingestion import get_chapter_for_page


class CheckChunkHitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.question = {
            "gold_page": 1,
            "gold_source_id": "doc-1",
            "evidence_quote": "full evidence phrase",
        }
        self.chunk = {
            "page": 1,
            "document_id": "doc-1",
            "text": "A full evidence phrase appears here.",
        }

    def test_requires_full_evidence_quote(self) -> None:
        self.chunk["text"] = "A full evidence is missing the ending."
        hit, details = check_chunk_hit(self.question, self.chunk)

        self.assertFalse(hit)
        self.assertFalse(details["evidence_match"])

    def test_accepts_complete_evidence_quote(self) -> None:
        hit, details = check_chunk_hit(self.question, self.chunk)

        self.assertTrue(hit)
        self.assertTrue(details["evidence_match"])

    def test_missing_evidence_quote_is_not_a_hit(self) -> None:
        self.question["evidence_quote"] = ""
        hit, details = check_chunk_hit(self.question, self.chunk)

        self.assertFalse(hit)
        self.assertFalse(details["evidence_match"])

    def test_requires_all_spans_for_multi_page_evidence(self) -> None:
        self.question.pop("evidence_quote")
        self.question["evidence_quotes"] = ["first span", "second span"]
        self.chunk["text"] = "first span only"

        hit, details = check_chunk_hit(self.question, self.chunk)

        self.assertFalse(hit)
        self.assertFalse(details["evidence_match"])


class ChapterPageMappingTests(unittest.TestCase):
    def test_chapter_six_starts_on_page_27(self) -> None:
        self.assertEqual(get_chapter_for_page(26), "Chương V")
        self.assertEqual(get_chapter_for_page(27), "Chương VI")


if __name__ == "__main__":
    unittest.main()
