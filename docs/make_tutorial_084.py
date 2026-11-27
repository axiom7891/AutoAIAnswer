"""基于 v0.2.82 教程，生成 v0.2.84 版（新增连续截图/端口回退说明）。"""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

from docx import Document
from docx.shared import Pt

BASE = Path(r"D:\OneDrive\Desktop\笔试\助手使用教程Ctrl-v0.2.82.docx")
DESKTOP = Path.home() / "Desktop"
TUTORIAL_DIR = Path(r"D:\OneDrive\Desktop\笔试")
REPO_DOCS = Path(r"D:\OneDrive\Desktop\所有笔试有关\AutoAIAnswer-CustomerC\docs")

VERSION_TEXT = (
    "本教程对应 v0.2.84（主版本）。这版还支持手机端代码换行、分段复制、电脑方向键遥控手机答案框。\n"
    "本版更新：连续截图改为一次一张（不会重复）、失败会自动把图放回缓存；本地端口被占用会自动换端口。"
)

MULTI_CAPTURE_TEXT = (
    "连续截图怎么用：先在控制台勾「启用多图快捷键」，之后 Ctrl+Shift+左键 每按一次加一张，"
    "最多 5 张（满了再截会替换最早的一张，日志里有提示）。\n"
    "Ctrl+Shift+右键 把这 5 张一起发给模型分析；如果分析失败（网络断、额度用完、Key 无效），"
    "图会自动放回缓存，修好网络再按一次右键就行，不用重新截。"
)

PORT_TEXT = (
    "另外：电脑上 8000 端口被别的软件或旧进程占用时，程序会自动改用 8001–8009，"
    "控制台显示的二维码和地址就是实际端口，手机直接扫它就行，不用手动改端口。"
)


def replace_text(paragraph, text: str) -> None:
    for run in paragraph.runs[1:]:
        run.text = ""
    if paragraph.runs:
        paragraph.runs[0].text = text
        paragraph.runs[0].font.size = Pt(17)
    else:
        run = paragraph.add_run(text)
        run.font.size = Pt(17)


def insert_after(anchor, document, text: str):
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    run.font.size = Pt(17)
    if anchor.runs:
        source_run = anchor.runs[0]
        if source_run.font.name:
            run.font.name = source_run.font.name
        if source_run._element.rPr is not None and source_run._element.rPr.rFonts is not None:
            run._element.get_or_add_rPr().append(copy.deepcopy(source_run._element.rPr.rFonts))
    anchor._p.addnext(paragraph._p)
    return paragraph


def find(document, prefix: str):
    for paragraph in document.paragraphs:
        if paragraph.text.strip().startswith(prefix):
            return paragraph
    raise LookupError(prefix)


def main() -> None:
    target = DESKTOP / "助手使用教程Ctrl-v0.2.84.docx"
    shutil.copyfile(BASE, target)
    document = Document(str(target))

    version = find(document, "本教程对应 v0.2.82")
    replace_text(version, VERSION_TEXT)

    multi = find(document, "搜题的方式有几种")
    insert_after(multi, document, MULTI_CAPTURE_TEXT)

    port = find(document, "电脑配合手机")
    insert_after(port, document, PORT_TEXT)

    document.save(str(target))
    print("saved", target)

    for folder in (TUTORIAL_DIR, REPO_DOCS):
        if folder.exists():
            shutil.copyfile(target, folder / target.name)
            print("copied to", folder)


if __name__ == "__main__":
    main()
