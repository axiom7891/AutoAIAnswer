"""生成《客户端笔试 · 使用教程与注意事项》图文文档。"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets_client_exam"
DESKTOP = Path.home() / "Desktop"
TARGET = DESKTOP / "客户端笔试使用教程-v0.2.80.docx"

GREEN = RGBColor(0x05, 0x96, 0x69)
GRAY = RGBColor(0x64, 0x74, 0x8B)



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

def set_font(document: Document) -> None:
    style = document.styles["Normal"]
    style.font.name = "Microsoft YaHei"
    style.font.size = Pt(10.5)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")


def heading(document: Document, text: str, level: int = 1) -> None:
    paragraph = document.add_heading(text, level=level)
    for run in paragraph.runs:
        run.font.name = "Microsoft YaHei"
        run.font.color.rgb = RGBColor(0x11, 0x18, 0x27)


def para(document: Document, text: str, size: float = 10.5, color: RGBColor | None = None, bold: bool = False):
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    paragraph.paragraph_format.space_after = Pt(6)
    return paragraph


def bullets(document: Document, items: list[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Bullet")
        run = paragraph.add_run(item)
        run.font.size = Pt(10.5)


def image(document: Document, name: str, caption: str, width_cm: float = 15.5) -> None:
    path = ASSETS / name
    if not path.exists():
        return
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run().add_picture(str(path), width=Cm(width_cm))
    note = document.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = note.add_run(caption)
    run.font.size = Pt(9)
    run.font.color.rgb = GRAY


def table(document: Document, rows: list[list[str]], widths: list[float] | None = None) -> None:
    grid = document.add_table(rows=len(rows), cols=len(rows[0]))
    grid.style = "Light Grid Accent 1"
    grid.alignment = WD_TABLE_ALIGNMENT.CENTER
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            cell = grid.cell(row_index, col_index)
            cell.text = ""
            run = cell.paragraphs[0].add_run(value)
            run.font.size = Pt(9.5)
            if row_index == 0:
                run.font.bold = True
            if widths:
                cell.width = Cm(widths[col_index])
    document.add_paragraph()


def build() -> None:
    document = Document()
    set_font(document)
    section = document.sections[0]
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)

    title = document.add_heading("客户端笔试 · 使用教程与注意事项", level=0)
    for run in title.runs:
        run.font.name = "Microsoft YaHei"
    para(document, "适用版本：v0.2.80（0.62 版 v0.2.70 同样可用）", size=10, color=GRAY)
    para(
        document,
        "适用场景：以桌面客户端形式运行的在线笔试（牛客、易考、北森、赛码、EAS 等）。"
        "这类考试和网页版最大的区别是：客户端独占全屏、会抢焦点、通常带防截屏，所以操作方式要跟着变。",
        size=10.5,
    )

    heading(document, "一、整体怎么配合", 1)
    bullets(
        document,
        [
            "电脑端：运行本软件，负责截图、把题目发给模型、把答案显示成悬浮字幕。",
            "手机端：同一 WiFi 下打开控制台显示的地址，用来看完整答案、翻页、复制。",
            "所有截图和字幕都绕开共享屏幕：屏幕共享 / 录屏里看不到它们。",
            "考试客户端本身以管理员权限运行时，本软件的快捷键仍然有效（轮询读取按键，不装键盘钩子）。",
        ],
    )
    image(document, "flow.png", "图 1  考前、考中、交卷三个阶段要做的事", 15.8)

    heading(document, "二、考前 10 分钟清单", 1)
    table(
        document,
        [
            ["顺序", "要做的事", "怎么确认做到"],
            ["1", "结束所有旧进程，只留一个实例", "任务管理器里只有一个 QQMusic-CustomerC.exe"],
            ["2", "填 Key、选模型", "点「保存模型配置」，日志显示已保存"],
            ["3", "（可选）导入题库", "「题库」里显示已导入条数"],
            ["4", "手机连同一 WiFi 打开页面", "手机能看到答案区、能点「截全屏」"],
            ["5", "打开「解决黑屏」", "按钮变成「已开启：目标窗口可见」"],
            ["6", "字幕透明度调到 55%–75%", "屏幕上字幕浅浅一层，能看清但不刺眼"],
            ["7", "关闭系统通知、手机静音", "考前不再弹出微信 / 邮件提醒"],
        ],
        widths=[1.4, 7.5, 7.0],
    )
    image(document, "console_cards.png", "图 2  控制台：「截图与手势」里的解决黑屏、字幕透明度、快捷键入口", 15.5)

    heading(document, "三、客户端笔试的 6 个坑和对策", 1)
    table(
        document,
        [
            ["坑", "表现", "对策"],
            ["全屏独占、抢焦点", "点一下别处，客户端就弹「离开考试页面」警告", "全程用鼠标手势和热键，不 Alt+Tab、不点控制台"],
            ["客户端自己防截屏", "截出来是黑屏 / 只有背景", "考前开「解决黑屏」（Alt+F）；仍黑说明目标受保护，改用手机端"],
            ["切屏被记录", "监考报告里出现「切屏 1 次」", "把控制台缩到托盘；需要看控制台时用托盘图标，不要用任务栏"],
            ["双机位摄像头拍到屏幕", "人工复核看到字幕", "字幕放屏幕最下沿或导航栏；透明度 55%–75%；颜色挑摄像头拍不出来的"],
            ["Alt+F 被客户端占用", "按 Alt+F 弹出客户端自己的菜单", "改用控制台按钮开关；或告诉我换成别的组合键"],
            ["旧实例 / 旧版本", "手机连到旧版、新功能没生效", "每次换版本前先结束所有旧进程，只开一个"],
        ],
        widths=[3.6, 5.6, 7.0],
    )

    heading(document, "四、进考场前的最后三步", 1)
    bullets(
        document,
        [
            "第一步：点「让目标窗口持续可见（解决黑屏）」，按钮变成绿色「已开启：目标窗口可见（点击还原）」。",
            "第二步：按 Alt+Z 确认字幕能显示/隐藏，透明度合适。",
            "第三步：手机端点一次「截全屏」，确认能收到答案（这一步同时验证了 WiFi 和模型）。",
        ],
    )
    image(document, "subtitle.png", "图 3  考试客户端 + 悬浮字幕 + 手机三处配合（示意图）", 15.8)

    heading(document, "五、考试中怎么取题", 1)
    table(
        document,
        [
            ["方式", "操作", "适合"],
            ["整屏（最省事）", "鼠标左键双击", "单选题、判断题，题目在屏幕中间"],
            ["整屏（稳妥）", "鼠标右键长按 2 秒", "客户端把双击吃掉时用这个"],
            ["框选", "左键长按 2 秒 → 拖框 → 松开", "一屏多题、或只想截题干"],
            ["自动截屏", "中键长按 1 秒 或 左键三连击", "连续做题、题目自动翻页的考试"],
            ["连拍", "Ctrl+Shift+左键（勾选多图快捷键）", "资料分析、长材料"],
        ],
        widths=[3.8, 7.6, 5.0],
    )
    para(
        document,
        "建议：平时用「左键双击」，遇到客户端吃掉双击或需要精确取题时，改用「右键长按 2 秒」或框选。",
        size=10,
        color=GRAY,
    )

    heading(document, "六、答案怎么看", 1)
    bullets(
        document,
        [
            "电脑：答案以半透明字幕浮在屏幕上，默认只显示结论，适合扫一眼就落笔。",
            "手机：完整解析、翻页、复制答案、代码块单独复制都在手机上，字号比电脑大。",
            "不想让字幕出现时按 Alt+Z 临时隐藏，需要时再按一次。",
        ],
    )
    image(document, "phone.png", "图 4  手机端答案页（示意）：截全屏、翻页、复制", 9.5)
    image(document, "hotkeys.png", "图 5  控制台「查看所有热键」弹窗：所有操作方式都在这", 13.5)

    heading(document, "七、交卷与收尾", 1)
    table(
        document,
        [
            ["步骤", "操作", "为什么"],
            ["1", "按 Alt+G 还原「解决黑屏」", "把目标窗口的保护状态恢复原样"],
            ["2", "按 Alt+Z 关闭字幕", "避免交卷后还挂在屏幕上"],
            ["3", "退出软件（托盘 → 退出）", "结束截图与热键监听"],
            ["4", "手机页面关掉", "断开与电脑的连接"],
        ],
        widths=[1.4, 8.0, 8.0],
    )

    heading(document, "八、注意事项（按重要性）", 1)
    number = 1
    items = [
        "只开一个实例：旧实例会占着 8000 端口，手机可能连到旧版。",
        "不要在考试中打开控制台：控制台是普通窗口，切过去会被记录「切屏」；用托盘图标或热键。",
        "「解决黑屏」只影响目标窗口：它不会让本软件的控制台或字幕暴露给共享屏幕。",
        "解决黑屏是持续生效的：退出软件或 Alt+G 才会还原，不会 2 分钟后自动失效。",
        "字幕位置：屏幕最下沿、导航栏、或摄像头照不到的一侧；不要放在额头附近。",
        "字幕颜色：选一个和背景接近、但自己看得清的颜色（浅灰、深蓝），比纯白更不显眼。",
        "手机放法：屏幕侧后方、屏幕亮度调低、开常亮但关自动亮度。",
        "不要用手机热点：部分机型电脑连不上；确实要热点，用第二台手机开给两台设备。",
        "网络不稳时：先把模型换成响应最快的，别在考试中改 Key。",
        "如果日志出现「快捷键冲突」：说明某个组合键被别的软件占了，换一种取题方式即可。",
        "如果日志出现「目标受保护」：说明考试端做了内核级保护，本软件不能解除，改用手机端。",
        "交卷前按顺序收尾：Alt+G → Alt+Z → 退出软件 → 手机关页面。",
    ]
    for item in items:
        paragraph = document.add_paragraph()
        run = paragraph.add_run(f"{number}. {item}")
        run.font.size = Pt(10.5)
        paragraph.paragraph_format.space_after = Pt(3)
        number += 1

    heading(document, "九、出问题怎么办", 1)
    table(
        document,
        [
            ["现象", "先查什么", "再怎么办"],
            ["截图全黑", "是否开了「解决黑屏」；是否给了屏幕录制权限", "按 Alt+F 重开一次；仍黑改用手机端"],
            ["字幕不显示", "「显示桌面流式悬浮答案」是否勾选；是否按过 Alt+Z", "再按一次 Alt+Z；重启软件"],
            ["手机打不开页面", "同一 WiFi？VPN 关了？8000 端口被占？", "换端口/关 VPN；用二维码重扫"],
            ["按了热键没反应", "软件是否在运行；是否只开了一个实例", "重启软件；改用鼠标手势"],
            ["答案不出来", "Key 是否有效、模型是否可用", "换一条模型路线；看日志里的报错"],
        ],
        widths=[3.6, 7.2, 6.4],
    )

    heading(document, "十、版本说明", 1)
    bullets(
        document,
        [
            "v0.2.80（主版本）：16 条模型路线、手机端代码换行/字号/自动巡览/分段复制、电脑方向键遥控手机答案框。",
            "v0.2.70（0.62 版）：11 条模型路线，其余操作方式与本文一致。",
            "两个版本都支持：左键双击截屏、Alt+Z 字幕、Alt+F/Alt+G 解决黑屏、查看所有热键。",
        ],
    )

    apply_disclaimer(document)
    document.save(str(TARGET))
    print("saved", TARGET)


if __name__ == "__main__":
    build()
