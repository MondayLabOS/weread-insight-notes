"""Offline checks for record binding, media portability and content preservation."""

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from image_manifest import prepare_images
from export_weread_notes import build_xml, build_markdown

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "one.png").write_bytes(PNG)
        (self.root / "two.png").write_bytes(PNG + b"second-original")
        self.book = {"bookId": "synthetic-book", "title": "测试书"}
        self.highlights = [
            {"chapterUid": 1, "range": "10-20", "markText": "[插图]", "mainChapterTitle": "第一章"},
            {"chapterUid": 2, "range": "10-20", "markText": "正文与脚注\ufffc", "mainChapterTitle": "第二章"},
        ]
        self.notes = [
            {"reviewId": "n1", "chapterUid": 1, "range": "10-20", "content": "我的原始心得", "mainChapterTitle": "第一章"},
            {"reviewId": "n2", "chapterUid": 1, "range": "30-40", "abstract": "关联原文", "content": "未匹配划线的心得", "mainChapterTitle": "第一章"},
        ]
        self.liked = [{"chapterUid": 1, "range": "10-20", "authorName": "作者", "content": "点赞观点"}]

    def entry(self, filename="one.png", uid=1, range_value="10-20"):
        return {"chapterUid": uid, "range": range_value, "localPath": filename}

    def prepare(self, entries, book_id="synthetic-book"):
        return prepare_images({"bookId": book_id, "images": entries}, self.root,
                              "synthetic-book", self.highlights, self.notes, self.root / "out")

    def test_images_stay_in_matching_record_before_notes(self):
        mapping, images = self.prepare([self.entry(), self.entry("two.png")])
        tree = ET.fromstring("<root>" + build_xml(self.book, self.highlights, self.notes, self.liked, mapping) + "</root>")
        items = list(tree.iter("li"))
        target = next(item for item in items if "我的原始心得" in "".join(item.itertext()))
        self.assertEqual([child.tag for child in target], ["p", "img", "img", "blockquote", "blockquote"])
        self.assertEqual([img.get("path") for img in target.iter("img")], ["@./" + i["localPath"] for i in images])
        footnote = next(item for item in items if "正文与脚注" in "".join(item.itertext()))
        self.assertEqual(len(list(footnote.iter("img"))), 0)
        plain = ET.fromstring("<root>" + build_xml(self.book, self.highlights, self.notes, self.liked) + "</root>")
        self.assertEqual("".join(plain.itertext()), "".join(tree.itertext()))
        markdown = build_markdown(self.book, self.highlights, self.notes, self.liked, mapping)
        self.assertLess(markdown.index("!["), markdown.index("我的原始心得"))
        self.assertTrue(all((self.root / "out" / i["localPath"]).exists() for i in images))

    def test_unpaired_personal_note_can_have_image(self):
        mapping, _ = self.prepare([self.entry(range_value="30-40")])
        tree = ET.fromstring("<root>" + build_xml(self.book, self.highlights, self.notes, [], mapping) + "</root>")
        target = next(e for e in tree.iter("li") if "未匹配划线的心得" in "".join(e.itertext()))
        self.assertEqual(len(list(target.iter("img"))), 1)
        self.assertIn("关联原文", "".join(target.itertext()))

    def test_markdown_keeps_double_digit_items_images_and_quotes_nested(self):
        highlights = [{"chapterUid": 1, "range": f"{i*10}-{i*10+1}", "markText": "正文", "mainChapterTitle": "第一章"}
                      for i in range(10)]
        notes = [{"reviewId": "tenth", "chapterUid": 1, "range": "90-91", "content": "第十条心得", "mainChapterTitle": "第一章"}]
        mapping, _ = prepare_images({"bookId": "synthetic-book", "images": [self.entry(range_value="90-91")]},
                                   self.root, "synthetic-book", highlights, notes, self.root / "out")
        from unittest.mock import patch
        # Keep all items in one category so numbering reaches ten.
        with patch("export_weread_notes.classify", return_value="核心观点"):
            markdown = build_markdown(self.book, highlights, notes, [], mapping)
        tenth = markdown[markdown.index("10. "):]
        self.assertIn("\n    ![", tenth)
        self.assertIn("\n    > 我的笔记：第十条心得", tenth)

    def test_duplicate_bytes_within_record_are_not_repeated(self):
        _, images = self.prepare([self.entry(), self.entry()])
        self.assertEqual(len(images), 1)

    def test_reject_wrong_book_and_unmatched_binding_before_copy(self):
        with self.assertRaises(ValueError):
            self.prepare([self.entry()], book_id="another-book")
        with self.assertRaises(ValueError):
            self.prepare([self.entry(), self.entry(uid=99)])
        self.assertFalse((self.root / "out").exists())

    def test_reject_changed_or_invalid_original_image(self):
        entry = self.entry()
        entry["sha256"] = "wrong-checksum"
        with self.assertRaises(ValueError):
            self.prepare([entry])
        (self.root / "not-image.png").write_text("not an image")
        with self.assertRaises(ValueError):
            self.prepare([self.entry("not-image.png")])

    def test_offline_cli_round_trip_preserves_data_and_media(self):
        payload = {"book": self.book, "highlights": self.highlights,
                   "personalThoughts": self.notes, "likedViewpoints": self.liked, "meta": {}}
        input_path = self.root / "input.json"
        input_path.write_text(json.dumps(payload))
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"bookId": "synthetic-book", "images": [self.entry()]}))
        command = [sys.executable, str(SCRIPTS / "export_weread_notes.py"), "--book-id", "synthetic-book"]
        env = {k: v for k, v in os.environ.items() if k != "WEREAD_API_KEY"}
        result = subprocess.run(command + ["--input-json", str(input_path), "--image-manifest", str(manifest),
                                "--out-dir", str(self.root / "first")], env=env, capture_output=True, text=True, check=True)
        outputs = json.loads(result.stdout)
        first = json.loads(Path(outputs["json"]).read_text())
        for key in payload:
            self.assertEqual(first[key], payload[key])
        result = subprocess.run(command + ["--input-json", outputs["json"], "--out-dir", str(self.root / "second")],
                                env=env, capture_output=True, text=True, check=True)
        second_outputs = json.loads(result.stdout)
        second = json.loads(Path(second_outputs["json"]).read_text())
        self.assertEqual(first, second)
        self.assertEqual((self.root / "second" / second["images"][0]["localPath"]).read_bytes(), PNG)
        xml = Path(second_outputs["xml"]).read_text()
        self.assertIn('<img path="@./images/', xml)

    def test_offline_cli_rejects_wrong_source_book(self):
        payload = {"book": self.book, "highlights": [], "personalThoughts": []}
        source = self.root / "source.json"
        source.write_text(json.dumps(payload))
        result = subprocess.run([sys.executable, str(SCRIPTS / "export_weread_notes.py"), "--book-id", "other",
                                 "--input-json", str(source), "--out-dir", str(self.root / "out")],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "out").exists())


if __name__ == "__main__":
    unittest.main()
