"""给 Word 文档加「声明」：正文首段 + 页脚，逐页可见。

用法：
    python docs/add_disclaimer.py 文件1.docx 文件2.docx ...

会先在同目录生成 .bak 备份，再原地修改。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

DISCLAIMER = (
    "声明：本教程仅用于允许使用辅助工具的练习、自测场景。"
    "仅作技术交流，任何违法用途与行为与作者无关。"
)
GRAY = RGBColor(0x6B, 0x72, 0x80)
FONT = "Microsoft YaHei"


def _style_run(run, size: float, color: RGBColor, bold: bool = False) -> None:
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)


def _shade(paragraph, fill: str = "F3F4F6") -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    shd = p_pr.makeelement(qn("w:shd"), {qn("w:val"): "clear", qn("w:color"): "auto", qn("w:fill"): fill})
    p_pr.append(shd)


def add_to_document(path: Path) -> tuple[bool, str]:
    document = Document(str(path))
    first = document.paragraphs[0] if document.paragraphs else None

    # 已经有声明就不重复加
    existing = "\n".join(p.text for p in document.paragraphs[:4])
    if "仅用于允许使用辅助工具的练习" in existing:
        return False, "已存在声明，跳过"

    paragraph = document.add_paragraph()
    run = paragraph.add_run(DISCLAIMER)
    _style_run(run, 9.5, GRAY, bold=False)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.space_before = Pt(2)
    paragraph.paragraph_format.space_after = Pt(10)
    _shade(paragraph)

    if first is not None:
        first._p.addprevious(paragraph._p)
    else:
        document.element.body.insert(0, paragraph._p)

    # 页脚：每页都带
    for section in document.sections:
        footer = section.footer
        target = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        for extra in footer.paragraphs[1:]:
            extra.text = ""
        target.text = ""
        run = target.add_run(DISCLAIMER)
        _style_run(run, 8, GRAY)
        target.alignment = WD_ALIGN_PARAGRAPH.CENTER

    document.save(str(path))
    return True, "已添加"


def main(paths: list[str]) -> None:
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            print("跳过（不存在）:", path)
            continue
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            shutil.copyfile(path, backup)
        changed, message = add_to_document(path)
        print(("已修改" if changed else "未修改"), path.name, "-", message)


if __name__ == "__main__":
    main(sys.argv[1:])
