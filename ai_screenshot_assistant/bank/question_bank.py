from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import threading
import unicodedata
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Iterable

from PIL import Image

from ai_screenshot_assistant.bank.ocr import OcrTextReader

BANK_VERSION = 1
IMAGE_HAMMING_THRESHOLD = 6
FUZZY_THRESHOLD = 0.86
MIN_QUESTION_CHARS = 4
MAX_REPORTED_MATCHES = 12

TEXT_SUFFIXES = frozenset({".csv", ".tsv", ".txt", ".json", ".xlsx", ".pdf", ".docx", ".doc"})
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})

_LEADING_NUMBER = re.compile(
    r"^\s*(?:第\s*\d{1,3}\s*题\s*[.、．:：]?|\d{1,3}\s*[.、．)）])\s*"
)
_QUESTION_KEYS = ("question", "q", "题目", "问题", "题干", "title")
_ANSWER_KEYS = ("answer", "a", "答案", "response", "解析答案")


@dataclass(frozen=True)
class BankEntry:
    answer: str
    question: str = ""
    image_hash: str = ""
    aspect: float = 0.0
    source: str = "text"


@dataclass(frozen=True)
class BankMatch:
    entry: BankEntry
    score: float = 1.0
    position: int = 0


def normalize_text(text: object) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    lines = [_LEADING_NUMBER.sub("", line) for line in value.splitlines()]
    value = "".join(lines).lower()
    return re.sub(r"[\W_]+", "", value)


def default_bank_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "AI Screenshot Assistant" / "question_bank.json"


def image_fingerprint(png_bytes: bytes) -> tuple[str, float]:
    with Image.open(io.BytesIO(png_bytes)) as image:
        image = image.convert("L")
        aspect = round(image.width / image.height, 3) if image.height else 0.0
        small = image.resize((9, 8), Image.Resampling.LANCZOS)
        pixels = small.tobytes()
    bits = 0
    for row in range(8):
        for column in range(8):
            left = pixels[row * 9 + column]
            right = pixels[row * 9 + column + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}", aspect


def hamming_distance(left: str, right: str) -> int:
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except (TypeError, ValueError):
        return 64


def _format_answer(entry: BankEntry, source_label: str, *, include_source: bool = True) -> str:
    answer = entry.answer.strip()
    if not answer:
        return ""
    body = answer if answer.startswith(("答案：", "答案:")) else f"答案：{answer}"
    if include_source and "解析" not in body:
        body += f"\n解析：题库匹配（{source_label}）"
    return body


def format_matches(matches: list[BankMatch], source_label: str) -> str:
    entries = [match.entry for match in matches if match.entry.answer.strip()]
    if not entries:
        return ""
    if len(entries) == 1:
        return _format_answer(entries[0], source_label)
    blocks: list[str] = []
    for index, entry in enumerate(entries[:MAX_REPORTED_MATCHES], start=1):
        question = entry.question.strip().replace("\n", " ")
        heading = f"【第{index}题】{question[:20]}" if question else f"【第{index}题】"
        blocks.append(f"{heading}\n{_format_answer(entry, source_label, include_source=False)}")
    blocks.append(f"（来自本地{source_label}，共匹配 {len(entries)} 题）")
    return "\n\n".join(blocks)


def _text_chunks(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    chunks: list[str] = []
    for start in range(len(lines)):
        for size in (1, 2, 3):
            if start + size <= len(lines):
                chunk = normalize_text("".join(lines[start:start + size]))
                if chunk:
                    chunks.append(chunk)
    return chunks or [normalize_text(text)]


class QuestionBank:
    def __init__(
        self,
        path: Path | str | None = None,
        entries: Iterable[BankEntry] | None = None,
        ocr: Callable[[bytes], str] | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else default_bank_path()
        self._entries: list[BankEntry] = list(entries or [])
        self._ocr = ocr or OcrTextReader()
        self._lock = threading.RLock()

    @classmethod
    def load(cls, path: Path | str | None = None, ocr: Callable[[bytes], str] | None = None) -> "QuestionBank":
        bank_path = Path(path) if path is not None else default_bank_path()
        entries: list[BankEntry] = []
        if bank_path.exists():
            try:
                data = json.loads(bank_path.read_text(encoding="utf-8-sig"))
                for item in data.get("entries", []):
                    if not isinstance(item, dict):
                        continue
                    answer = str(item.get("answer") or "").strip()
                    if not answer:
                        continue
                    try:
                        aspect = float(item.get("aspect") or 0.0)
                    except (TypeError, ValueError):
                        aspect = 0.0
                    entries.append(
                        BankEntry(
                            answer=answer,
                            question=str(item.get("question") or ""),
                            image_hash=str(item.get("image_hash") or ""),
                            aspect=aspect,
                            source=str(item.get("source") or "text"),
                        )
                    )
            except (OSError, ValueError, TypeError):
                entries = []
        return cls(bank_path, entries, ocr=ocr)

    def save(self) -> None:
        payload = {
            "version": BANK_VERSION,
            "entries": [asdict(entry) for entry in self._snapshot()],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        temporary.replace(self.path)

    def _snapshot(self) -> list[BankEntry]:
        with self._lock:
            return list(self._entries)

    @property
    def text_count(self) -> int:
        return sum(1 for entry in self._snapshot() if entry.question and not entry.image_hash)

    @property
    def image_count(self) -> int:
        return sum(1 for entry in self._snapshot() if entry.image_hash)

    @property
    def total_count(self) -> int:
        return len(self._snapshot())

    def summary(self) -> str:
        if self.total_count == 0:
            return "未导入题库"
        return f"题库 {self.total_count} 题（文本 {self.text_count} / 截图 {self.image_count}）"

    def clear(self) -> None:
        with self._lock:
            self._entries = []
        self.save()

    def add_pair(self, question: str, answer: str) -> bool:
        question = str(question or "").strip()
        answer = str(answer or "").strip()
        if not answer:
            return False
        key = normalize_text(question)
        with self._lock:
            if key:
                for index, entry in enumerate(self._entries):
                    if entry.source == "text" and normalize_text(entry.question) == key:
                        self._entries[index] = BankEntry(answer=answer, question=question, source="text")
                        return True
            self._entries.append(BankEntry(answer=answer, question=question, source="text"))
            return True

    def add_image(self, png_bytes: bytes, answer: str, name: str = "") -> bool:
        answer = str(answer or "").strip()
        if not answer:
            return False
        image_hash, aspect = image_fingerprint(png_bytes)
        with self._lock:
            for index, entry in enumerate(self._entries):
                if entry.image_hash == image_hash:
                    self._entries[index] = BankEntry(
                        answer=answer,
                        question=name or entry.question,
                        image_hash=image_hash,
                        aspect=aspect,
                        source="image",
                    )
                    return True
            self._entries.append(
                BankEntry(answer=answer, question=name, image_hash=image_hash, aspect=aspect, source="image")
            )
            return True

    def add_pairs(self, pairs: Iterable[tuple[str, str]]) -> int:
        added = 0
        for question, answer in pairs:
            if self.add_pair(question, answer):
                added += 1
        return added

    def _match_image(self, png_bytes: bytes) -> BankEntry | None:
        entries = [entry for entry in self._snapshot() if entry.image_hash]
        if not entries:
            return None
        image_hash, aspect = image_fingerprint(png_bytes)
        best: tuple[int, BankEntry] | None = None
        for entry in entries:
            if entry.aspect and aspect and not (0.85 <= entry.aspect / aspect <= 1.18):
                continue
            distance = hamming_distance(entry.image_hash, image_hash)
            if distance > IMAGE_HAMMING_THRESHOLD:
                continue
            if best is None or distance < best[0]:
                best = (distance, entry)
        return best[1] if best else None

    def answer_for_text(self, text: str) -> str | None:
        matches = self.matches_for_text(text)
        if not matches:
            return None
        return format_matches(matches, "文本题库")

    def matches_for_text(self, text: str) -> list[BankMatch]:
        entries = [entry for entry in self._snapshot() if entry.question and not entry.image_hash]
        if not entries or not str(text or "").strip():
            return []
        normalized = normalize_text(text)
        if not normalized:
            return []
        exact: list[tuple[int, int, BankEntry]] = []
        for entry in entries:
            question = normalize_text(entry.question)
            if len(question) < MIN_QUESTION_CHARS:
                continue
            position = normalized.find(question)
            if position >= 0:
                exact.append((position, len(question), entry))
        if exact:
            exact.sort(key=lambda item: (item[0], -item[1]))
            selected: list[tuple[int, int, BankEntry]] = []
            for position, length, entry in exact:
                if any(
                    other_position <= position
                    and position + length <= other_position + other_length
                    for other_position, other_length, _ in selected
                ):
                    continue
                selected = [
                    item
                    for item in selected
                    if not (position <= item[0] and item[0] + item[1] <= position + length)
                ]
                selected.append((position, length, entry))
            selected.sort(key=lambda item: item[0])
            return [BankMatch(entry=entry, position=position) for position, _length, entry in selected]

        chunks = _text_chunks(text)
        chunk_grams: set[str] = set()
        for chunk in chunks:
            chunk_grams.update(chunk[index:index + 3] for index in range(max(0, len(chunk) - 2)))
        best_score = 0.0
        best_entry: BankEntry | None = None
        for entry in entries:
            question = normalize_text(entry.question)
            if len(question) < 6:
                continue
            question_grams = {question[index:index + 3] for index in range(len(question) - 2)}
            if not question_grams & chunk_grams:
                continue
            for chunk in chunks:
                length_ratio = len(question) / max(1, len(chunk))
                if length_ratio < 0.5 or length_ratio > 1.8:
                    continue
                score = SequenceMatcher(None, question, chunk).ratio()
                if score > best_score:
                    best_score = score
                    best_entry = entry
        if best_entry is not None and best_score >= FUZZY_THRESHOLD:
            return [BankMatch(entry=best_entry, score=best_score)]
        return []

    def find_answer(self, png_bytes: bytes, ocr_text: str | None = None) -> str | None:
        image_match = self._match_image(png_bytes)
        if image_match is not None:
            return _format_answer(image_match, "截图题库")
        if not any(entry.question for entry in self._snapshot() if not entry.image_hash):
            return None
        text = ocr_text
        if text is None:
            text = self._ocr(png_bytes)
        if not text:
            return None
        return self.answer_for_text(text)


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _delimiter_for(text: str, suffix: str) -> str:
    if suffix == ".tsv":
        return "\t"
    if suffix == ".csv":
        sample = text[:4096]
        try:
            return csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
        except csv.Error:
            return "\t" if "\t" in sample else ","
    return "\t" if "\t" in text else ","


def _is_header(row: list[str]) -> bool:
    normalized = {cell.strip().lower() for cell in row if cell.strip()}
    return bool(normalized & {"题目", "问题", "题干", "question", "q"}) and bool(
        normalized & {"答案", "answer", "a"}
    )


def _pairs_from_rows(rows: Iterable[Iterable[Any]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    first = True
    for row in rows:
        cells = [str(cell or "").strip() for cell in row]
        cells = [cell for cell in cells if cell]
        if not cells:
            continue
        if first:
            first = False
            if _is_header(cells):
                continue
        if len(cells) < 2:
            continue
        pairs.append((cells[0], "\n".join(cells[1:])))
    return pairs


def _pairs_from_prefixed_lines(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    question = ""
    answers: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^(?:题目|问题|题干|Q|Question)\s*[:：]\s*(.+)$", stripped, re.IGNORECASE)
        if match:
            if question and answers:
                pairs.append((question, "\n".join(answers)))
            question = match.group(1).strip()
            answers = []
            continue
        match = re.match(r"^(?:答案|Answer|A)\s*[:：]\s*(.+)$", stripped, re.IGNORECASE)
        if match:
            answers.append(match.group(1).strip())
    if question and answers:
        pairs.append((question, "\n".join(answers)))
    return pairs


def _pairs_from_numbered_lines(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    question = ""
    answer: list[str] = []
    in_answer = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        question_match = re.match(r"^(?:第\s*)?(\d{1,4})\s*[.、．)）]\s*(.+)$", stripped)
        answer_match = re.match(
            r"^(?:答案|参考答案|正确答案|Answer)\s*[:：]\s*(.*)$",
            stripped,
            re.IGNORECASE,
        )
        if question_match:
            if question and in_answer and answer:
                pairs.append((question, "\n".join(answer)))
                question = ""
                answer = []
                in_answer = False
            if not question:
                question = question_match.group(2).strip()
            elif not in_answer:
                question += "\n" + question_match.group(2).strip()
            continue
        if answer_match and question:
            in_answer = True
            if answer_match.group(1).strip():
                answer.append(answer_match.group(1).strip())
            continue
        if question and in_answer:
            answer.append(stripped)
        elif question:
            question += "\n" + stripped
    if question and in_answer and answer:
        pairs.append((question, "\n".join(answer)))
    return pairs


def _dedupe_pairs(pairs: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for question, answer in pairs:
        question = str(question or "").strip()
        answer = str(answer or "").strip()
        if not answer:
            continue
        key = (normalize_text(question), answer)
        if key in seen:
            continue
        seen.add(key)
        result.append((question, answer))
    return result


def _pairs_from_document_text(text: str) -> list[tuple[str, str]]:
    pairs = _pairs_from_prefixed_lines(text)
    if not pairs:
        pairs = _pairs_from_numbered_lines(text)
    if not pairs:
        rows = [re.split(r"\t+", line) for line in text.splitlines() if "\t" in line]
        pairs = _pairs_from_rows(rows)
    return _dedupe_pairs(pairs)


def _pairs_from_docx(path: Path) -> list[tuple[str, str]]:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("缺少 python-docx，无法读取 Word 题库") from exc
    document = Document(str(path))
    pairs: list[tuple[str, str]] = []
    for table in document.tables:
        rows = [[cell.text for cell in row.cells] for row in table.rows]
        pairs.extend(_pairs_from_rows(rows))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    pairs.extend(_pairs_from_document_text(text))
    return _dedupe_pairs(pairs)


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("缺少 pypdf，无法读取 PDF 题库") from exc
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise ValueError(f"PDF 无法打开：{exc}") from exc
    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("PDF 已加密，请先解除密码") from exc
    pages: list[str] = []
    for index in range(min(len(reader.pages), 50)):
        try:
            pages.append(reader.pages[index].extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages)


def _ocr_pdf(path: Path) -> str:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError("扫描版 PDF 需要 pypdfium2 才能识别") from exc
    reader = OcrTextReader()
    lines: list[str] = []
    document = pdfium.PdfDocument(str(path))
    try:
        for index in range(min(len(document), 30)):
            page = document[index]
            bitmap = page.render(scale=2)
            image = bitmap.to_pil()
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            lines.append(reader(buffer.getvalue()))
    finally:
        document.close()
    return "\n".join(lines)


def _pairs_from_pdf(path: Path) -> list[tuple[str, str]]:
    text = _pdf_text(path)
    if len(normalize_text(text)) < 10 and "答案" not in text and "answer" not in text.lower():
        text = _ocr_pdf(path)
    return _pairs_from_document_text(text)


def _pairs_from_json(text: str) -> list[tuple[str, str]]:
    data = json.loads(text)
    items: list[Any]
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and isinstance(data.get("questions"), list):
        items = data["questions"]
    elif isinstance(data, dict):
        items = [{"question": key, "answer": value} for key, value in data.items()]
    else:
        return []
    pairs: list[tuple[str, str]] = []
    for item in items:
        if isinstance(item, dict):
            question = next((str(item[key]).strip() for key in _QUESTION_KEYS if key in item), "")
            answer = next((str(item[key]).strip() for key in _ANSWER_KEYS if key in item), "")
            if isinstance(item.get("answer"), list):
                answer = "\n".join(str(part) for part in item["answer"])
            if answer:
                pairs.append((question, answer))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            pairs.append((str(item[0]).strip(), str(item[1]).strip()))
    return pairs


def load_pairs_from_file(path: Path | str) -> list[tuple[str, str]]:
    bank_path = Path(path)
    suffix = bank_path.suffix.lower()
    if suffix not in TEXT_SUFFIXES:
        raise ValueError(f"不支持的题库文件类型：{suffix or bank_path.name}")
    if suffix == ".doc":
        raise ValueError("暂不支持旧版 .doc，请在 Word 中另存为 .docx 后再上传")
    if suffix == ".docx":
        return _pairs_from_docx(bank_path)
    if suffix == ".pdf":
        return _pairs_from_pdf(bank_path)
    if suffix == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("缺少 openpyxl，无法读取 Excel 题库") from exc
        workbook = load_workbook(bank_path, read_only=True, data_only=True)
        try:
            sheet = workbook.active
            rows = [list(row) for row in sheet.iter_rows(values_only=True)]
        finally:
            workbook.close()
        return _pairs_from_rows(rows)
    text = _read_text(bank_path)
    if suffix == ".json":
        return _pairs_from_json(text)
    if suffix == ".txt":
        document_pairs = _pairs_from_document_text(text)
        if document_pairs:
            return document_pairs
    delimiter = _delimiter_for(text, suffix)
    rows = csv.reader(io.StringIO(text), delimiter=delimiter)
    return _pairs_from_rows(rows)


def import_bank_file(bank: QuestionBank, path: Path | str) -> int:
    pairs = load_pairs_from_file(path)
    added = bank.add_pairs(pairs)
    if added:
        bank.save()
    return added
