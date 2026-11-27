"""把旧版《笔试助手使用教程Ctrl.docx》更新到 v0.2.74：保留原风格、原始截图，只改文案并补新功能。"""

from __future__ import annotations

import shutil
from pathlib import Path

from docx import Document
from docx.shared import Pt

SRC = Path(r"D:\OneDrive\Desktop\笔试\笔试助手使用教程Ctrl.docx")
DST = Path(r"D:\OneDrive\Desktop\笔试\笔试助手使用教程Ctrl-v0.2.80.docx")

TEXT_0 = "可以支持只用电脑，或者电脑配合手机（操作在手机上）。"
TEXT_1 = (
    "只用电脑的话就用鼠标隐蔽按键（具体按键看控制台）：左键长按 2 秒框选题目，"
    "右键长按 2 秒截整屏，左键双击 直接截整屏（最省事）。另外几个常用键：Ctrl 单键截全屏（客户 C，控制台里手动勾选）、"
    "鼠标中键长按 1 秒 / 左键三连击开关「自动截全屏」、Alt+Z 显示/隐藏悬浮字幕、"
    "Alt+F 开关「解决黑屏」、Alt+G 立即还原。\n"
    "截图和字幕都是绕开共享屏幕的。新版默认不勾「共享屏幕时隐藏控制台」，需要藏控制台的时候自己去勾。"
)
TEXT_2 = (
    "电脑配合手机，需要同一个 wifi 下面，不能手机开热点给电脑（有的手机可以，自己试），"
    "可以用第 2 个手机开热点给手机和电脑用。（如果电脑端可以用、手机扫码打不开，是环境问题，先查："
    "是不是同一个 wifi、vpn 关没关、虚拟机端口有没有禁用（网络和 Internet 的高级网络设置）、"
    "8000 端口有没有被别的软件占用；自己排不出来再找我。）\n"
    "升级版本之前先在任务管理器把所有 QQMusic 进程结束掉，只开一个：旧实例会占着 8000 端口，"
    "手机可能连到旧版，看起来就像新功能没生效。"
)
TEXT_4 = (
    "控制台现在是卡片式的，功能按用途分组：快捷操作、手机端、模型与密钥、截图与手势、悬浮字幕、"
    "外观、题库、快捷键、系统 Prompt、运行日志。不需要的功能把勾去掉就行；想换浅色主题或字体，在「外观」里改。"
)
TEXT_6 = (
    "apikey 填你自己的，不会找可以问豆包或者问我。填了哪家的 key 就能用哪家的模型，没填的用不了。"
    "这版一共 16 条路线：豆包 4 条、OpenRouter 6 条国产，另加 GPT-4o / GPT-4.1 / DeepSeek V4.1 / "
    "Claude Opus 5.5 / GPT-6 Luna，还有 DeepSeek 官方 1 条。\n"
    "新模型有些 OpenRouter 还没上线，选了它会自动退回默认模型重试一次，不会让截图卡住。"
)
TEXT_13 = (
    "当然电脑端直接看也可以：手机点按钮，电脑看悬浮字幕；或者电脑端鼠标隐蔽截图，电脑看字幕。"
)
TEXT_19 = (
    "像图三这种更适合完全依靠电脑配合鼠标隐蔽截图，需要开启字幕。字幕透明度现在可以 0–100% 调，"
    "0% 等于完全看不见，建议 55%–75%；文字颜色也能改，挑一个摄像头拍不出来的颜色，"
    "放在导航栏或者屏幕最下面最隐蔽。"
)
TEXT_25 = (
    "提示：不需要的功能就把勾去掉；控制台和字幕都是绕开共享屏幕的；程序可以缩到托盘，"
    "任务栏里就看不到它在跑了。"
)

BLACKOUT_NOTE = (
    "解决黑屏（实验）：有些考试端会让截图变黑，点控制台「解决黑屏」里的「让目标窗口持续可见」就行；"
    "它只对覆盖截图区域的窗口解除保护，本软件的控制台和字幕不受影响，开了会一直保持，"
    "考试中途按 Alt+F 可开关、Alt+G 立即还原。截图异常自动修复已经默认开启，不用再勾选。"
)
HELP_NOTE = (
    "忘了键位就点控制台「快捷键」卡片里的「查看所有热键」，会弹窗列出全部操作方式和热键。"
)
PHONE_ITEMS = [
    "手机端这版加了几个看长答案的功能：",
    "· 代码自动换行：默认开，长代码不会右边被裁掉。",
    "· 代码字号：自适应 / 特小 / 小 / 较小 / 中 / 大，自适应会把整段代码缩到一屏。",
    "· 自动巡览：答案框自己慢慢上下滚、代码块左右滚，手不碰手机也能看完。",
    "· 每个代码块右上角有「复制代码」；答案区还能按每 N 个字符「分段复制」，方便贴进有字数限制的输入框。",
    "· 接键盘的话：Shift+W/S 上下翻页，Shift+A/D 代码左右滚。",
]
REMOTE_LINE = (
    "电脑端可以直接用方向键遥控手机答案框（不用组合键）：↑↓ 翻页，←→ 代码左右滚；"
    "控制台「手机端」里的开关默认勾选。"
)
VERSION_NOTE = (
    "版本差异：如果你用的是 0.62 那份（v0.2.70），模型是 11 条（没有 Claude / GPT-6 / DeepSeek V4.1），"
    "手机端没有代码换行和分段复制，电脑方向键也不能遥控手机答案框，其余用法一样。"
)
FAQ_ITEMS = [
    "常见问题：",
    "· 手机打不开页面：先确认同一个 wifi、vpn 关掉、8000 端口没被别的软件占用。",
    "· 双击没反应：多半被杀毒拦了，把目录加信任区再重新解压。",
    "· 截图全黑 / 只有背景：自动修复默认开着；还黑就用「解决黑屏」，或右键管理员身份运行。"
    "· 解决黑屏没反应：目标程序可能受保护，日志里会写；这时改用手机端看答案。",
    "· 按了快捷键没反应：确认软件在运行、只开了一个实例；中键要按住满 1 秒再松。",
]



def apply_disclaimer(document) -> None:
    """在正文首段前插入声明，并写入页脚，保证每页可见。"""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor
    from add_disclaimer import DISCLAIMER, _shade, _style_run

    text_so_far = "\n".join(p.text for p in document.paragraphs[:4])
    if "仅用于允许使用辅助工具的练习" not in text_so_far:
        paragraph = document.add_paragraph()
        _style_run(paragraph.add_run(DISCLAIMER), 9.5, RGBColor(0x6B, 0x72, 0x80))
        paragraph.paragraph_format.space_after = Pt(10)
        _shade(paragraph)
        if document.paragraphs[:-1]:
            document.paragraphs[0]._p.addprevious(paragraph._p)
        else:
            document.element.body.insert(0, paragraph._p)
    for section in document.sections:
        footer = section.footer
        target = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        target.text = ""
        _style_run(target.add_run(DISCLAIMER), 8, RGBColor(0x6B, 0x72, 0x80))
        target.alignment = WD_ALIGN_PARAGRAPH.CENTER

def replace_text(paragraph, text: str) -> None:
    if not paragraph.runs:
        run = paragraph.add_run(text)
        run.font.size = Pt(17)
        return
    paragraph.runs[0].text = text
    for run in paragraph.runs[1:]:
        run.text = ""


def insert_after(anchor, text: str, size: float = 17, bold: bool = False):
    paragraph = anchor.part.document.add_paragraph()
    run = paragraph.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    anchor._p.addnext(paragraph._p)
    return paragraph


def find_paragraph(document, prefix: str):
    for paragraph in document.paragraphs:
        if paragraph.text.strip().startswith(prefix):
            return paragraph
    raise LookupError(prefix)


def main() -> None:
    shutil.copyfile(SRC, DST)
    document = Document(str(DST))

    replacements = [
        ("可以支持只用电脑", TEXT_0),
        ("只用电脑的话就用鼠标", TEXT_1),
        ("电脑配合手机", TEXT_2),
        ("控制台有很多功能", TEXT_4),
        ("apikey", TEXT_6),
        ("当然电脑端直接看", TEXT_13),
        ("像图三这种", TEXT_19),
        ("提示：当不需要其他功能", TEXT_25),
    ]
    for prefix, new_text in replacements:
        replace_text(find_paragraph(document, prefix), new_text)

    anchor = find_paragraph(document, "当然电脑端直接看")
    for item in PHONE_ITEMS:
        anchor = insert_after(anchor, item, size=15)
    insert_after(anchor, REMOTE_LINE, size=17)

    anchor = find_paragraph(document, "提示：")
    anchor = insert_after(anchor, BLACKOUT_NOTE, size=15)
    anchor = insert_after(anchor, HELP_NOTE, size=15)
    anchor = insert_after(anchor, VERSION_NOTE, size=15)
    for item in FAQ_ITEMS:
        anchor = insert_after(anchor, item, size=15 if item.startswith("·") else 17)

    apply_disclaimer(document)
    document.save(str(DST))
    print("saved", DST)


if __name__ == "__main__":
    main()
