#!/usr/bin/env python3
"""Export WeRead highlights/notes into Markdown, JSON, and Lark-compatible XML."""

from __future__ import annotations

import argparse
import collections
import html
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path


API = "https://i.weread.qq.com/api/agent/gateway"
SKILL_VERSION = "1.0.3"


def api_key() -> str:
    key = os.environ.get("WEREAD_API_KEY", "").strip()
    if key:
        return key
    try:
        key = subprocess.check_output(["launchctl", "getenv", "WEREAD_API_KEY"], text=True).strip()
    except Exception:
        key = ""
    if not key:
        raise SystemExit("WEREAD_API_KEY is not set.")
    return key


def call(body: dict, key: str) -> dict:
    payload = json.dumps({**body, "skill_version": SKILL_VERSION}, ensure_ascii=False).encode()
    req = urllib.request.Request(
        API,
        data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        ret = json.loads(resp.read().decode())
    if isinstance(ret, dict) and ret.get("errcode") not in (None, 0):
        raise RuntimeError(ret)
    return ret


def norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def esc(text: str | None) -> str:
    return html.escape(str(text or ""), quote=False).replace("\n", "<br/>")


def main_for_chapters(chapters: list[dict]) -> dict[int, dict]:
    main_for: dict[int, dict] = {}
    current: dict | None = None
    for chapter in sorted(chapters, key=lambda c: c.get("chapterIdx", 999999)):
        if chapter.get("level") == 1:
            current = chapter
        main_for[chapter.get("chapterUid")] = current or chapter
    return main_for


def get_reviews(book_id: str, key: str) -> list[dict]:
    reviews: list[dict] = []
    synckey = 0
    while True:
        body = {"api_name": "/review/list/mine", "bookid": book_id, "count": 200}
        if synckey:
            body["synckey"] = synckey
        ret = call(body, key)
        reviews.extend(ret.get("reviews", []))
        if not ret.get("hasMore"):
            return reviews
        next_key = ret.get("synckey")
        if not next_key or next_key == synckey:
            return reviews
        synckey = next_key


def liked_viewpoints(book_id: str, highlights: list[dict], key: str) -> list[dict]:
    by_chapter: dict[int, list[str]] = collections.defaultdict(list)
    seen = set()
    for highlight in highlights:
        uid = highlight.get("chapterUid")
        range_value = highlight.get("range")
        if uid and range_value and (uid, range_value) not in seen:
            seen.add((uid, range_value))
            by_chapter[uid].append(range_value)

    liked: list[dict] = []
    for chapter_uid, ranges in sorted(by_chapter.items()):
        for i in range(0, len(ranges), 10):
            req_ranges = [{"range": r, "count": 20, "maxIdx": 0, "synckey": 0} for r in ranges[i : i + 10]]
            ret = call(
                {
                    "api_name": "/book/readreviews",
                    "bookId": book_id,
                    "chapterUid": chapter_uid,
                    "reviews": req_ranges,
                },
                key,
            )
            for range_reviews in ret.get("reviews", []) or []:
                range_value = range_reviews.get("range")
                for page_review in range_reviews.get("pageReviews", []) or []:
                    review = page_review.get("review") or {}
                    if review.get("isLike") == 1:
                        liked.append(
                            {
                                "chapterUid": chapter_uid,
                                "range": range_value or review.get("range") or "",
                                "reviewId": review.get("reviewId") or page_review.get("reviewId"),
                                "content": review.get("content") or "",
                                "abstract": review.get("abstract") or "",
                                "authorName": (review.get("author") or {}).get("name") or "",
                            }
                        )
    return liked


def default_categories(book_title: str, chapter_title: str = "") -> list[tuple[str, list[str]]]:
    title = f"{book_title} {chapter_title}"
    if "金钱" in title or "money" in title.lower():
        return [
            ("心理动机", ["心理", "情绪", "羞愧", "恐惧", "内疚", "安全"]),
            ("关系与边界", ["关系", "夫妻", "父母", "朋友", "控制", "边界"]),
            ("行为模式", ["消费", "节约", "贪婪", "慷慨", "偷窃", "秘密"]),
            ("改变与行动", ["改变", "选择", "探索", "承认", "接受"]),
        ]
    return [("核心观点", []), ("个人触发", []), ("行动启发", [])]


def classify(book_title: str, chapter_title: str, record: dict) -> str:
    cats = default_categories(book_title, chapter_title)
    text = " ".join(
        [
            record.get("highlight", ""),
            " ".join(record.get("notes", [])),
            " ".join(v.get("content", "") for v in record.get("liked", [])),
            record.get("sub", ""),
        ]
    ).lower()
    best = cats[0][0]
    best_score = -1
    for name, keywords in cats:
        score = sum(1 for keyword in keywords if keyword.lower() in text)
        if score > best_score:
            best = name
            best_score = score
    if best_score <= 0 and record.get("notes") and len(cats) > 1:
        return cats[1][0]
    return best


def build_records(book_id: str, include_liked: bool, key: str) -> tuple[dict, list[dict], list[dict], list[dict], dict]:
    chapter_info = call({"api_name": "/book/chapterinfo", "bookId": book_id}, key)
    bookmarks = call({"api_name": "/book/bookmarklist", "bookId": book_id}, key)
    raw_reviews = get_reviews(book_id, key)

    chapters = chapter_info.get("chapters", [])
    by_uid = {c.get("chapterUid"): c for c in chapters}
    main_for = main_for_chapters(chapters)

    reviews = []
    for item in raw_reviews:
        review = item.get("review") or {}
        uid = review.get("chapterUid")
        chapter = by_uid.get(uid, {})
        main = main_for.get(uid) or chapter
        reviews.append(
            {
                "reviewId": review.get("reviewId") or item.get("reviewId"),
                "chapterUid": uid,
                "range": review.get("range") or "",
                "content": norm(review.get("content")),
                "abstract": norm(review.get("abstract")),
                "chapterTitle": review.get("chapterTitle") or chapter.get("title") or review.get("chapterName") or "",
                "chapterIdx": review.get("chapterIdx") or chapter.get("chapterIdx"),
                "mainChapterIdx": main.get("chapterIdx"),
                "mainChapterTitle": main.get("title") or "",
                "createTime": review.get("createTime") or 0,
            }
        )

    highlights = []
    for item in bookmarks.get("updated", []):
        uid = item.get("chapterUid")
        chapter = by_uid.get(uid, {})
        main = main_for.get(uid) or chapter
        highlights.append(
            {
                "chapterUid": uid,
                "range": item.get("range") or "",
                "markText": norm(item.get("markText")),
                "chapterTitle": chapter.get("title") or "",
                "chapterIdx": chapter.get("chapterIdx"),
                "mainChapterIdx": main.get("chapterIdx"),
                "mainChapterTitle": main.get("title") or "",
                "createTime": item.get("createTime") or 0,
            }
        )

    liked = liked_viewpoints(book_id, highlights, key) if include_liked else []
    return bookmarks.get("book") or {"bookId": book_id}, highlights, reviews, liked, {"chapters": chapters}


def build_xml(book: dict, highlights: list[dict], reviews: list[dict], liked: list[dict]) -> str:
    thoughts_by_key: dict[tuple, list[dict]] = collections.defaultdict(list)
    for review in reviews:
        thoughts_by_key[(review.get("chapterUid"), review.get("range"))].append(review)

    liked_by_key: dict[tuple, list[dict]] = collections.defaultdict(list)
    for item in liked:
        liked_by_key[(item.get("chapterUid"), item.get("range"))].append(item)

    used_review_ids = set()
    records_by_chapter: dict[tuple, list[dict]] = collections.OrderedDict()

    def chapter_key(item: dict) -> tuple:
        return (item.get("mainChapterIdx") or 999999, item.get("mainChapterTitle") or "未命名章节")

    for highlight in sorted(highlights, key=lambda x: (x.get("mainChapterIdx") or 999999, x.get("chapterIdx") or 999999, x.get("createTime") or 0)):
        key = chapter_key(highlight)
        match_key = (highlight.get("chapterUid"), highlight.get("range"))
        notes = thoughts_by_key.get(match_key, [])
        for note in notes:
            if note.get("reviewId"):
                used_review_ids.add(note["reviewId"])
        records_by_chapter.setdefault(key, []).append(
            {
                "kind": "highlight",
                "highlight": highlight.get("markText") or "",
                "notes": [note.get("content") for note in notes if note.get("content")],
                "liked": liked_by_key.get(match_key, []),
                "sub": highlight.get("chapterTitle") or "",
            }
        )

    for note in sorted(reviews, key=lambda x: (x.get("mainChapterIdx") or 999999, x.get("chapterIdx") or 999999, x.get("createTime") or 0)):
        if note.get("reviewId") in used_review_ids:
            continue
        key = chapter_key(note)
        match_key = (note.get("chapterUid"), note.get("range"))
        records_by_chapter.setdefault(key, []).append(
            {
                "kind": "thought_only",
                "highlight": note.get("abstract") or "",
                "notes": [note.get("content")] if note.get("content") else [],
                "liked": liked_by_key.get(match_key, []),
                "sub": note.get("chapterTitle") or "",
            }
        )

    parts = [
        f"<title>《{esc(book.get('title') or '微信读书')}》划线优先笔记</title>",
        "<callout emoji=\"📌\" background-color=\"light-yellow\" border-color=\"yellow\"><p>整理口径：一级标题为书籍大章；二级标题为内容分类；编号条目优先展示原文划线；如果这条划线有你的个人笔记或你点赞过的观点，则放在下方引用块中。</p></callout>",
    ]
    book_title = book.get("title") or ""
    for (_idx, title), records in records_by_chapter.items():
        buckets: dict[str, list[dict]] = collections.OrderedDict()
        for name, _keywords in default_categories(book_title, title):
            buckets[name] = []
        for record in records:
            buckets.setdefault(classify(book_title, title, record), []).append(record)
        parts.append(f"<h1>{esc(title)}</h1>")
        for category, category_records in buckets.items():
            if not category_records:
                continue
            parts.append(f"<h2>{esc(category)}</h2><ol>")
            for record in category_records:
                label = "原文划线" if record.get("kind") == "highlight" else "关联原文"
                body = f"<p><b>{label}：</b>{esc(record.get('highlight'))}</p>" if record.get("highlight") else ""
                for note in record.get("notes", []):
                    body += f"<blockquote><b>我的笔记：</b>{esc(note)}</blockquote>"
                for viewpoint in record.get("liked", []):
                    author = f"（{viewpoint.get('authorName')}）" if viewpoint.get("authorName") else ""
                    body += f"<blockquote><b>我点赞的观点{esc(author)}：</b>{esc(viewpoint.get('content'))}</blockquote>"
                parts.append(f"<li>{body or '<p>（空内容）</p>'}</li>")
            parts.append("</ol>")
    return "\n".join(parts)


def build_markdown(book: dict, highlights: list[dict], reviews: list[dict], liked: list[dict]) -> str:
    thoughts_by_key: dict[tuple, list[dict]] = collections.defaultdict(list)
    for review in reviews:
        thoughts_by_key[(review.get("chapterUid"), review.get("range"))].append(review)

    liked_by_key: dict[tuple, list[dict]] = collections.defaultdict(list)
    for item in liked:
        liked_by_key[(item.get("chapterUid"), item.get("range"))].append(item)

    used_review_ids = set()
    records_by_chapter: dict[tuple, list[dict]] = collections.OrderedDict()

    def chapter_key(item: dict) -> tuple:
        return (item.get("mainChapterIdx") or 999999, item.get("mainChapterTitle") or "未命名章节")

    for highlight in sorted(highlights, key=lambda x: (x.get("mainChapterIdx") or 999999, x.get("chapterIdx") or 999999, x.get("createTime") or 0)):
        key = chapter_key(highlight)
        match_key = (highlight.get("chapterUid"), highlight.get("range"))
        notes = thoughts_by_key.get(match_key, [])
        for note in notes:
            if note.get("reviewId"):
                used_review_ids.add(note["reviewId"])
        records_by_chapter.setdefault(key, []).append(
            {
                "kind": "highlight",
                "highlight": highlight.get("markText") or "",
                "notes": [note.get("content") for note in notes if note.get("content")],
                "liked": liked_by_key.get(match_key, []),
                "sub": highlight.get("chapterTitle") or "",
            }
        )

    for note in sorted(reviews, key=lambda x: (x.get("mainChapterIdx") or 999999, x.get("chapterIdx") or 999999, x.get("createTime") or 0)):
        if note.get("reviewId") in used_review_ids:
            continue
        key = chapter_key(note)
        match_key = (note.get("chapterUid"), note.get("range"))
        records_by_chapter.setdefault(key, []).append(
            {
                "kind": "thought_only",
                "highlight": note.get("abstract") or "",
                "notes": [note.get("content")] if note.get("content") else [],
                "liked": liked_by_key.get(match_key, []),
                "sub": note.get("chapterTitle") or "",
            }
        )

    def quote(label: str, text: str) -> str:
        return "\n".join(f"> {line}" for line in f"{label}：{text}".splitlines())

    book_title = book.get("title") or "微信读书"
    parts = [
        f"# 《{book_title}》划线优先笔记",
        "",
        "整理口径：一级标题为书籍大章；二级标题为内容分类；编号条目优先展示原文划线；如果这条划线有你的个人笔记或你点赞过的观点，则放在下方引用块中。",
        "",
    ]
    for (_idx, title), records in records_by_chapter.items():
        buckets: dict[str, list[dict]] = collections.OrderedDict()
        for name, _keywords in default_categories(book_title, title):
            buckets[name] = []
        for record in records:
            buckets.setdefault(classify(book_title, title, record), []).append(record)

        parts.extend([f"# {title}", ""])
        for category, category_records in buckets.items():
            if not category_records:
                continue
            parts.extend([f"## {category}", ""])
            for index, record in enumerate(category_records, start=1):
                label = "原文划线" if record.get("kind") == "highlight" else "关联原文"
                highlight = record.get("highlight") or "（空内容）"
                parts.append(f"{index}. {label}：{highlight}")
                for note in record.get("notes", []):
                    parts.append(quote("我的笔记", note))
                for viewpoint in record.get("liked", []):
                    author = f"（{viewpoint.get('authorName')}）" if viewpoint.get("authorName") else ""
                    parts.append(quote(f"我点赞的观点{author}", viewpoint.get("content") or ""))
                parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-id", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--out-dir", default="exports")
    parser.add_argument("--include-liked", action="store_true")
    args = parser.parse_args()

    key = api_key()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    book, highlights, reviews, liked, meta = build_records(args.book_id, args.include_liked, key)
    base_name = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", args.title or book.get("title") or args.book_id).strip("-")
    export = {"book": book, "highlights": highlights, "personalThoughts": reviews, "likedViewpoints": liked, "meta": meta}

    json_path = out_dir / f"{base_name}-weread-notes.json"
    xml_path = out_dir / f"{base_name}-notes.xml"
    md_path = out_dir / f"{base_name}-insight-notes.md"

    json_path.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    xml_path.write_text(build_xml(book, highlights, reviews, liked), encoding="utf-8")
    md_path.write_text(build_markdown(book, highlights, reviews, liked), encoding="utf-8")
    print(json.dumps({"xml": str(xml_path), "json": str(json_path), "markdown": str(md_path), "highlights": len(highlights), "notes": len(reviews), "liked": len(liked)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
