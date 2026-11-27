"""基于现有教程，给两个最近版本各生成一份（v0.2.82 主版本 / v0.2.73 0.62 版）。

只做增补：版本行、模型与 Key 说明（Google 直连、自定义模型）、答案格式、选型建议。
原有图片、段落、顺序保持不变。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

BASE = Path(r"D:\OneDrive\Desktop\助手使用教程Ctrl-v0.2.70.docx")
DESKTOP = Path.home() / "Desktop"
REPO_DOCS = Path(r"D:\OneDrive\Desktop\AutoAIAnswer-CustomerC\docs")
TUTORIAL_DIR = Path(r"D:\OneDrive\Desktop\笔试")

GRAY = RGBColor(0x6B, 0x72, 0x80)
BODY_PT = 17

VARIANTS = [
    {
        "name": "v0.2.82",
        "label": "v0.2.82（主版本）",
        "count": "19",
        "openrouter": "13 条（Qwen 四条、GLM、MiniMax、Gemini 3.1 Pro、Claude Opus 5.5、GPT-6 Luna、GPT-4o、GPT-4.1、DeepSeek V4.1、自定义占位）",
        "extra": "，这版还支持手机端代码换行、分段复制，以及电脑方向键遥控手机答案框",
    },
    {
        "name": "v0.2.73",
        "label": "v0.2.73（0.62 版）",
        "count": "14",
        "openrouter": "7 条（Qwen 四条、GLM、MiniMax、Gemini 3.1 Pro）",
        "extra": "，这版没有 GPT-4o / GPT-4.1 / Claude / GPT-6，其余操作和主版本一样",
    },
]


def body_run(document, text: str, size: float = BODY_PT, color: RGBColor | None = None):
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    return paragraph


def replace_paragraph(paragraph, text: str) -> None:
    for run in paragraph.runs[1:]:
        run.text = ""
    if paragraph.runs:
        paragraph.runs[0].text = text
        paragraph.runs[0].font.size = Pt(BODY_PT)
    else:
        run = paragraph.add_run(text)
        run.font.size = Pt(BODY_PT)


def insert_after(anchor, document, text: str, size: float = BODY_PT):
    paragraph = body_run(document, text, size)
    anchor._p.addnext(paragraph._p)
    return paragraph


def find(document, prefix: str):
    for paragraph in document.paragraphs:
        if paragraph.text.strip().startswith(prefix):
            return paragraph
    raise LookupError(prefix)


def build(variant: dict) -> Path:
    target = DESKTOP / f"助手使用教程Ctrl-{variant['name']}.docx"
    shutil.copyfile(BASE, target)
    document = Document(str(target))

    # 1) 版本行（声明之后）
    version_text = f"本教程对应 {variant['label']}{variant['extra']}。"
    first = document.paragraphs[0]
    version_para = body_run(document, version_text, size=11, color=GRAY)
    version_para.paragraph_format.space_after = Pt(8)
    first._p.addnext(version_para._p)

    # 2) 模型与 Key 段（替换 apikey 段）
    model_text = (
        f"apikey 填你自己的，不会找可以问豆包或者问我。填了哪家的 key 就能用哪家的模型，没填的用不了。\n"
        f"这版一共 {variant['count']} 条路线：豆包 4 条、OpenRouter {variant['openrouter']}、"
        f"Google 官方直连 1 条、DeepSeek 官方 1 条。\n"
        f"模型名后面的「（快 / 准确一般）」这类描述已经全部去掉，选模型只看名字就行，避免被不准确的描述误导。"
    )
    anchor = find(document, "apikey")
    replace_paragraph(anchor, model_text)

    # 3) Google 直连
    google_text = (
        "Google 官方 Key（新）：模型列表里的「Google Gemini 3.1 Pro」是直连 Google 的，不经过 OpenRouter。"
        "去 Google AI Studio 建一个 Key（AIza 开头），填到「Google Key（可选）」里，保存后选这条模型就能用。"
        "行测的图形推理、数量关系这类题，Gemini 3.1 Pro 和 Claude Opus 5.5 都比较稳，可以两条都试，看哪个更对你的题型。"
    )
    anchor = insert_after(anchor, document, google_text)

    # 4) 自定义模型 ID
    custom_text = (
        "自定义模型 ID（新）：OpenRouter 上新模型、或者名字对不上时用这条。去 openrouter.ai/models 复制完整 ID"
        "（形如 google/gemini-3.1-pro-preview），粘到「自定义模型 ID」里，模型选「OpenRouter 自定义模型」，保存即可。"
        "留空时这条会显示「未填写模型 ID」，不会误调用。"
    )
    anchor = insert_after(anchor, document, custom_text)

    # 5) 答案格式
    format_text = (
        "答案格式（新）：模型卡片里多了一个「答案格式」，四档可选——\n"
        "· 答案 + 解析（默认）：先结论再一两句解析，适合需要看思路的题；\n"
        "· 只要答案：只给一行结论，不写解析，时间紧的时候用；\n"
        "· 只要选项字母：选择题只给 A/B/C/D（多选给 A、C），贴答案最快；\n"
        "· 只要第几个：只给「第 2 个」这种序号，适合选项被打乱、或只想记位置的题。\n"
        "选完会记住，下次打开还是这个设置。"
    )
    anchor = insert_after(anchor, document, format_text)

    # 6) 选型建议
    tip_text = (
        "选模型的建议：图形推理、数量关系用 Gemini 3.1 Pro 或 Claude Opus 5.5；言语、常识用 Qwen 235B 就够快；"
        "代码题用 DeepSeek V4.1 或 GPT-4.1；自动截屏连刷、只求速度时用 Qwen Flash 或 DeepSeek 官方。"
    )
    insert_after(anchor, document, tip_text)

    # 7) 失败切换说明补上 Google
    try:
        failover = find(document, "某条路线调不通")
        replace_paragraph(
            failover,
            "某条路线调不通（额度用完、模型没上线、Key 没权限）时，软件会切到另一家已经填了 key 的模型继续跑；"
            "如果两条都失败，就在「模型」里换一条再试。\n"
            "搜题调用 AI 模型，使用模型是要消耗 token，考试前确认下自己的余额够不够考完，别做到一半搜不了了。",
        )
    except LookupError:
        pass

    document.save(str(target))
    return target


def main() -> None:
    made = [build(variant) for variant in VARIANTS]
    for path in made:
        shutil.copyfile(path, REPO_DOCS / path.name)
        shutil.copyfile(path, TUTORIAL_DIR / path.name)
        print("saved", path)


if __name__ == "__main__":
    main()
