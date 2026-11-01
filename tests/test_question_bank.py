from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw

from ai_screenshot_assistant.bank.question_bank import (
    QuestionBank,
    image_fingerprint,
    hamming_distance,
    import_bank_file,
    load_pairs_from_file,
    normalize_text,
)


def _pattern_png(offset: int = 0) -> bytes:
    image = Image.new("RGB", (240, 120), "white")
    draw = ImageDraw.Draw(image)
    for x in range(0, 240, 24):
        draw.rectangle([x + offset, 0, x + offset + 12, 120], fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_normalize_removes_numbering_punctuation_and_width() -> None:
    assert normalize_text("1. 下列哪个是质数？") == normalize_text("下列哪个是质数")
    assert normalize_text("ＡＢＣ，１２３") == "abc123"


def test_text_bank_matches_exact_question(tmp_path: Path) -> None:
    bank = QuestionBank(tmp_path / "bank.json", ocr=lambda _png: "1. 下列哪个是质数？\nA.4 B.6 C.7 D.9")
    bank.add_pair("下列哪个是质数？", "C")

    answer = bank.find_answer(b"not-an-image")

    assert answer == "答案：C\n解析：题库匹配（文本题库）"


def test_text_bank_matches_multiple_questions_in_order(tmp_path: Path) -> None:
    bank = QuestionBank(tmp_path / "bank.json")
    bank.add_pair("第一题：水的化学式是什么？", "H2O")
    bank.add_pair("第二题：太阳从哪边升起？", "东方")

    answer = bank.answer_for_text("第一题：水的化学式是什么？\n第二题：太阳从哪边升起？")

    assert answer is not None
    assert "【第1题】" in answer
    assert "H2O" in answer
    assert "【第2题】" in answer
    assert "东方" in answer


def test_text_bank_tolerates_small_ocr_difference(tmp_path: Path) -> None:
    bank = QuestionBank(tmp_path / "bank.json")
    bank.add_pair("下列哪个是质数", "C")

    answer = bank.answer_for_text("1. 下列哪个数是质数?\nA.4 B.6 C.7 D.9")

    assert answer is not None
    assert "答案：C" in answer


def test_text_bank_does_not_match_unrelated_question(tmp_path: Path) -> None:
    bank = QuestionBank(tmp_path / "bank.json")
    bank.add_pair("下列哪个是质数", "C")

    assert bank.answer_for_text("请简述 TCP 三次握手的过程") is None


def test_image_bank_matches_identical_screenshot_without_ocr(tmp_path: Path) -> None:
    png = _pattern_png()
    bank = QuestionBank(
        tmp_path / "bank.json",
        ocr=lambda _png: (_ for _ in ()).throw(AssertionError("OCR should not run")),
    )
    assert bank.add_image(png, "B") is True

    assert bank.find_answer(png) == "答案：B\n解析：题库匹配（截图题库）"


def test_image_bank_rejects_different_screenshot(tmp_path: Path) -> None:
    bank = QuestionBank(tmp_path / "bank.json")
    bank.add_image(_pattern_png(0), "B")

    assert hamming_distance(*[image_fingerprint(_pattern_png(offset))[0] for offset in (0, 12)]) > 6
    assert bank.find_answer(_pattern_png(12)) is None


def test_bank_persists_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "bank.json"
    bank = QuestionBank(path)
    bank.add_pair("题目一是什么", "答案一")
    bank.add_image(_pattern_png(), "答案二", "截图一.png")
    bank.save()

    reloaded = QuestionBank.load(path)

    assert reloaded.total_count == 2
    assert reloaded.text_count == 1
    assert reloaded.image_count == 1
    assert reloaded.answer_for_text("题目一是什么") == "答案：答案一\n解析：题库匹配（文本题库）"


def test_bank_load_accepts_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "bank.json"
    payload = {"version": 1, "entries": [{"answer": "答案", "question": "题目内容", "source": "text"}]}
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    assert QuestionBank.load(path).total_count == 1


def test_csv_import_supports_header_and_quoted_cells(tmp_path: Path) -> None:
    path = tmp_path / "bank.csv"
    path.write_text('题目,答案\n"1,2,3 的和是多少？",6\n水的化学式,H2O\n', encoding="utf-8-sig")

    pairs = load_pairs_from_file(path)
    bank = QuestionBank(tmp_path / "bank.json")
    assert bank.add_pairs(pairs) == 2
    assert "答案：6" in (bank.answer_for_text("1,2,3 的和是多少？") or "")


def test_json_import_supports_mapping_and_question_list(tmp_path: Path) -> None:
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"题目一": "答案一"}, ensure_ascii=False), encoding="utf-8")
    listing = tmp_path / "listing.json"
    listing.write_text(
        json.dumps({"questions": [{"question": "题目二", "answer": "答案二"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert load_pairs_from_file(mapping) == [("题目一", "答案一")]
    assert load_pairs_from_file(listing) == [("题目二", "答案二")]


def test_excel_import(tmp_path: Path) -> None:
    from openpyxl import Workbook

    path = tmp_path / "bank.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["题目", "答案"])
    sheet.append(["Excel 题目", "Excel 答案"])
    workbook.save(path)

    assert load_pairs_from_file(path) == [("Excel 题目", "Excel 答案")]


def test_import_bank_file_saves_to_disk(tmp_path: Path) -> None:
    path = tmp_path / "bank.csv"
    path.write_text("题目,答案\n题目一,答案一\n", encoding="utf-8")
    bank = QuestionBank(tmp_path / "saved.json")

    assert import_bank_file(bank, path) == 1
    assert QuestionBank.load(tmp_path / "saved.json").total_count == 1


def test_numbered_txt_question_and_answer_blocks(tmp_path: Path) -> None:
    path = tmp_path / "numbered.txt"
    path.write_text(
        "1. 水的化学式是什么？\n答案：H2O\n解析：两个氢一个氧\n"
        "2. 太阳从哪边升起？\n答案：东方\n",
        encoding="utf-8",
    )

    pairs = load_pairs_from_file(path)

    assert pairs[0][0] == "水的化学式是什么？"
    assert "H2O" in pairs[0][1]
    assert pairs[1] == ("太阳从哪边升起？", "东方")


def test_word_docx_import_supports_paragraphs_and_tables(tmp_path: Path) -> None:
    path = tmp_path / "bank.docx"
    document = Document()
    document.add_paragraph("1. Word 题目一")
    document.add_paragraph("答案：Word 答案一")
    table = document.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "题目"
    table.rows[0].cells[1].text = "答案"
    table.rows[1].cells[0].text = "Word 题目二"
    table.rows[1].cells[1].text = "Word 答案二"
    document.save(path)

    pairs = load_pairs_from_file(path)

    assert ("Word 题目一", "Word 答案一") in pairs
    assert ("Word 题目二", "Word 答案二") in pairs


PDF_FIXTURE = base64.b64decode(
    "JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2JqCjIgMCBvYmoK"
    "PDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2JqCjMgMCBvYmoKPDwgL1R5"
    "cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIgNzkyXSAvUmVzb3VyY2VzIDw8IC9G"
    "b250IDw8IC9GMSA0IDAgUiA+PiA+PiAvQ29udGVudHMgNSAwIFIgPj4KZW5kb2JqCjQgMCBvYmoKPDwgL1R5"
    "cGUgL0ZvbnQgL1N1YnR5cGUgL1R5cGUxIC9CYXNlRm9udCAvSGVsdmV0aWNhID4+CmVuZG9iago1IDAgb2Jq"
    "Cjw8IC9MZW5ndGggNzcgPj4Kc3RyZWFtCkJUIC9GMSAxMiBUZiA3MiA3MjAgVGQgKFF1ZXN0aW9uOiBXaGF0"
    "IGlzIDErMT8pIFRqIDAgLTI0IFRkIChBbnN3ZXI6IDIpIFRqIEVUCmVuZHN0cmVhbQplbmRvYmoKeHJlZgow"
    "IDYKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDA5IDAwMDAwIG4gCjAwMDAwMDAwNTggMDAwMDAgbiAK"
    "MDAwMDAwMDExNSAwMDAwMCBuIAowMDAwMDAwMjQxIDAwMDAwIG4gCjAwMDAwMDAzMTEgMDAwMDAgbiAKdHJh"
    "aWxlcgo8PCAvU2l6ZSA2IC9Sb290IDEgMCBSID4+CnN0YXJ0eHJlZgo0MzgKJSVFT0YK"
)


def test_pdf_import_extracts_question_and_answer(tmp_path: Path) -> None:
    path = tmp_path / "bank.pdf"
    path.write_bytes(PDF_FIXTURE)

    assert load_pairs_from_file(path) == [("What is 1+1?", "2")]

