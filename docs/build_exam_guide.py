"""生成两份考试使用说明 DOCX：v0.2.74（主版本）与 v0.2.64（0.62 副本）。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

FONT = "微软雅黑"
ACCENT = RGBColor(0x1F, 0x8F, 0x6B)
MUTED = RGBColor(0x5B, 0x66, 0x75)



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

def set_east_asian(run, font: str = FONT) -> None:
    run.font.name = font
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), font)
    rfonts.set(qn("w:ascii"), font)
    rfonts.set(qn("w:hAnsi"), font)


def style_document(document: Document) -> None:
    normal = document.styles["Normal"]
    normal.font.size = Pt(10.5)
    normal.font.name = FONT
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.35
    for name, size in (("Heading 1", 16), ("Heading 2", 12.5), ("Heading 3", 11)):
        style = document.styles[name]
        style.font.name = FONT
        style.font.size = Pt(size)
        style.font.color.rgb = ACCENT
        style.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        style.paragraph_format.space_before = Pt(12 if name == "Heading 1" else 8)
        style.paragraph_format.space_after = Pt(6)
    section = document.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)


def shade(cell, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def add_title(document: Document, title: str, subtitle: str, meta: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = paragraph.add_run(title)
    set_east_asian(run)
    run.font.size = Pt(24)
    run.font.bold = True
    run.font.color.rgb = ACCENT

    sub = document.add_paragraph()
    run = sub.add_run(subtitle)
    set_east_asian(run)
    run.font.size = Pt(12)
    run.font.color.rgb = MUTED

    info = document.add_paragraph()
    run = info.add_run(meta)
    set_east_asian(run)
    run.font.size = Pt(9.5)
    run.font.color.rgb = MUTED


def add_paragraph(document: Document, text: str, bold: bool = False) -> None:
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    set_east_asian(run)
    run.font.bold = bold


def add_bullets(document: Document, items: list[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(2)
        run = paragraph.add_run(item)
        set_east_asian(run)


def add_steps(document: Document, items: list[str]) -> None:
    for index, item in enumerate(items, start=1):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.left_indent = Cm(0.6)
        paragraph.paragraph_format.first_line_indent = Cm(-0.6)
        run = paragraph.add_run(f"{index}. ")
        set_east_asian(run)
        run.font.bold = True
        run = paragraph.add_run(item)
        set_east_asian(run)


def add_table(document: Document, header: list[str], rows: list[list[str]], widths: list[float]) -> None:
    table = document.add_table(rows=1, cols=len(header))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for index, cell in enumerate(table.rows[0].cells):
        cell.text = ""
        run = cell.paragraphs[0].add_run(header[index])
        set_east_asian(run)
        run.font.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(cell, "1F8F6B")
        cell.width = Cm(widths[index])
    for row_values in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row_values):
            cells[index].text = ""
            run = cells[index].paragraphs[0].add_run(str(value))
            set_east_asian(run)
            run.font.size = Pt(9.5)
            cells[index].width = Cm(widths[index])
    document.add_paragraph()


def add_callout(document: Document, title: str, body: str) -> None:
    table = document.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.rows[0].cells[0]
    shade(cell, "EEF7F3")
    cell.text = ""
    paragraph = cell.paragraphs[0]
    run = paragraph.add_run(title)
    set_east_asian(run)
    run.font.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = ACCENT
    paragraph2 = cell.add_paragraph()
    run = paragraph2.add_run(body)
    set_east_asian(run)
    run.font.size = Pt(9.5)
    document.add_paragraph()


def build(path: Path, version: str, edition: str, routes: str, extras: dict[str, object]) -> None:
    document = Document()
    style_document(document)

    add_title(
        document,
        "AI 搜题助手 · 考试使用说明",
        f"版本 {version}（{edition}）",
        f"适用系统：Windows 10/11 · 文档生成日期：{date.today().isoformat()} · 建议考前 10 分钟按第三章逐项检查",
    )

    document.add_heading("一、这份软件能做什么", level=1)
    add_paragraph(
        document,
        "电脑上看题、手机上看答案。用鼠标框选或截取整个屏幕，软件把题目发给你配置的视觉模型，"
        "答案同时在「控制台」「手机网页」「桌面悬浮字幕」三处显示，主屏可以始终停在考试页面。",
    )
    add_table(
        document,
        ["能力", "说明"],
        [
            ["框选搜题", "左键长按 2 秒框选题目区域，松开后再点终点，自动分析"],
            ["整屏搜题", "右键长按 2 秒截取当前屏幕；部分版本支持单击 Ctrl 截屏（客户 C）"],
            ["连续截图", "滚动页面截 2–5 张，一次发给模型做资料分析"],
            ["手机看答案", "同一 WiFi 扫码打开网页，答案逐字推送，可放大、翻页、复制"],
            ["悬浮字幕", "答案以半透明文字浮在屏幕上，Alt+Z 显示/隐藏"],
            ["自动截屏", "鼠标中键长按 1 秒 / 左键三连击开关，按设定间隔自动截全屏并分析"],
            ["解决黑屏", "考试端让截图变黑时，只对目标窗口解除保护；Alt+F 开关、Alt+G 还原"],
            ["本地题库", "上传 Excel/CSV/PDF/Word/截图题库，命中直接返回，省额度"],
        ],
        [4.2, 12.6],
    )

    document.add_heading("二、和其他版本的差别", level=1)
    add_table(
        document,
        ["项目", f"{version}", "另一版本"],
        [
            ["模型路线", routes, extras["other_routes"]],
            ["手机端代码块", extras["code_block"], extras["other_code_block"]],
            ["电脑方向键遥控手机", extras["remote_arrows"], extras["other_remote"]],
            ["界面", "深色卡片式控制台，可切浅色", "同为深色卡片式控制台"],
            ["字幕透明度", "0–100%（0 = 完全透明）", "0–100%（0 = 完全透明）"],
        ],
        [4.0, 6.4, 6.4],
    )

    document.add_heading("三、第一次使用（装好到能出答案）", level=1)
    add_steps(
        document,
        [
            "解压到一个固定目录（例如 D:\\kaoshi\\），路径不要带空格和中文以外的特殊符号；不要放在 C 盘临时目录。",
            "双击 QQMusic-CustomerC.exe。首次启动 Windows 可能弹「已保护你的电脑」，点「更多信息 → 仍要运行」。",
            "控制台打开后，在「模型与密钥」卡片填入至少一把 Key（DeepSeek / OpenRouter / 豆包任选），"
            "推荐 OpenRouter，可选的模型最多；填完点「保存模型配置」，看到「已保存」即生效。",
            "在「手机端」卡片等待链接生成，手机连同一个 WiFi，扫二维码打开网页；顶部显示「电脑已连接」即配对成功。",
            "把手机调成常亮、关闭省电模式，放在键盘旁边或支架上。",
            "随便截一道题试一次，确认电脑、手机、字幕三处都有答案，再进考场。",
        ],
    )
    add_callout(
        document,
        "第一次务必做的事",
        "在「外观」卡片确认「控制台主题」为黑色（默认），字体为系统默认；在「悬浮字幕」卡片把透明度调到 55%–75%，"
        "既能看清又不挡题。所有设置会自动保存，下次打开沿用。",
    )

    document.add_heading("四、考场前 10 分钟检查清单", level=1)
    add_table(
        document,
        ["#", "检查项", "怎么确认"],
        [
            ["1", "只有一个程序实例", "任务管理器搜 QQMusic，只应有一个进程组；多了全部结束再重开"],
            ["2", "端口 8000 没被旧版占用", "手机重新扫码能打开页面即正常；打不开先结束所有旧实例"],
            ["3", "Key 已保存", "「模型与密钥」显示「已保存」且右上角芯片显示当前模型"],
            ["4", "手机已连接", "手机页面顶部「电脑已连接」，电脑端「手机端」显示配对链接"],
            ["5", "字幕能显示", "按 Alt+Z 一次，屏幕上出现/消失半透明字幕"],
            ["6", "中键能开关自动截屏", "中键长按 1 秒 / 左键三连击，「自动截全屏」勾选状态翻转"],
            ["7", "共享屏幕设置符合监考要求", "「共享屏幕时隐藏控制台」默认不勾选；需要时手动勾选"],
            ["8", "电量与静音", "笔记本接电源；手机不锁屏；系统通知全部关闭"],
            ["9", "题库可选", "如需题库，提前上传并确认显示「已导入 N 条」"],
        ],
        [1.0, 5.4, 10.4],
    )

    document.add_heading("五、考试中怎么用", level=1)
    document.add_heading("5.1 单题：框选", level=2)
    add_steps(
        document,
        [
            "鼠标移到题目左上角，按住左键不放，约 2 秒后松开（会看到框选提示）。",
            "移动到题目右下角，单击左键，软件自动截图并分析。",
            "答案 3–8 秒内出现在控制台；手机页面和悬浮字幕同步刷新。",
            "需要看解析时看手机（答案区可滚动），主屏保持考试页面不动。",
        ],
    )
    document.add_heading("5.2 整屏 / 多题", level=2)
    add_steps(
        document,
        [
            "右键长按 2 秒，截取当前屏幕全屏发送；一屏多题会按题号分别作答。",
            "也可点控制台的「截取当前屏幕」按钮（绿色主按钮）。",
            "客户 C 版本支持单击 Ctrl 截全屏：在「截图与手势」里勾选「Ctrl 单键松开截全屏搜题」。",
        ],
    )
    document.add_heading("5.3 资料分析：多图一起发", level=2)
    add_steps(
        document,
        [
            "先滚到材料第一段，点「连续截图」（或 Ctrl+Shift+左键）。",
            "滚动页面，再截 1–4 张，最多 5 张，按钮上会显示「分析连续截图缓存（N）」。",
            "点「分析连续截图缓存」一次性发送，模型会把多张图拼起来读。",
            "发完如需重来，点「清空缓存」。",
        ],
    )
    document.add_heading("5.4 手机端看答案", level=2)
    add_bullets(
        document,
        [
            "答案逐字推送，不用等全部生成；长答案用「上一页 / 下一页」或开「自动翻页」。",
            "「复制答案」把完整答案复制到剪贴板；" + extras["chunk_note"],
            "手机熄屏会断开实时推送，务必设为常亮；息屏后重新打开页面即可继续。",
            "手机与电脑必须同一网络；用手机热点时，电脑连热点后重新扫码。",
        ],
    )
    if extras["code_block_extra"]:
        document.add_heading("5.5 代码题：手机端看不全怎么办（本版本支持）", level=2)
        add_bullets(
            document,
            [
                "答案区下方「代码自动换行」默认开启，长行自动折行，右侧不再被裁掉。",
                "「代码字号」可选自适应 / 特小 / 小 / 较小 / 中 / 大；自适应会把整段代码缩到一屏内。",
                "「自动巡览」开启后答案框自己慢慢上下滚、代码块左右滚，手不碰手机也能看完。",
                "每个代码块右上角有「复制代码」，只复制这一块。",
                "「分段复制」设好每段字数（默认 200），点「复制下一段」分次粘贴到答题框。",
                "外接键盘：Shift+W/S 上下翻页，Shift+A/D 代码左右滚。",
            ],
        )
    document.add_heading("5.6 悬浮字幕", level=2)
    add_bullets(
        document,
        [
            "Alt+Z 显示 / 隐藏；字幕只显示答案首行，适合快速扫一眼。",
            "「字幕透明度」0–100% 可调：0% 完全看不见，建议 55%–75%。",
            "字幕位置可以拖动；换分辨率后会自动拉回屏幕内。",
        ],
    )
    if extras["remote_arrows_detail"]:
        document.add_heading("5.7 电脑方向键遥控手机答案框（本版本支持）", level=2)
        add_bullets(
            document,
            [
                "在电脑上直接按 ↑ / ↓：手机答案框翻页；按 ← / →：手机里的代码块左右滚动。",
                "不需要任何组合键；方向键在其他软件里照常可用。",
                "控制台「手机端」卡片里的「方向键 ↑ ↓ ← → 直接遥控手机答案框」默认勾选，取消则停用。",
                "手机页面没反应时，先确认手机页面开着且显示「电脑已连接」。",
            ],
        )

    document.add_heading("六、快捷键总表", level=1)
    add_table(
        document,
        ["快捷键", "作用", "备注"],
        [
            ["左键长按 2 秒 + 单击终点", "框选题目", "最常用"],
            ["右键长按 2 秒", "整屏截题", "一屏多题"],
            ["Ctrl 单击", "整屏截题", "需在设置里勾选（客户 C）"],
            ["Ctrl+Shift+左键", "连续截图", "需勾选「启用多图快捷键」"],
            ["Ctrl+Shift+右键", "分析连续截图缓存", "同上"],
            ["左键双击", "截取当前屏幕（最省事）", "轮询实现，考试端也能用"],
            ["鼠标中键长按 1 秒 / 左键三连击", "开关自动截全屏", "两种都可以"],
            ["Alt+Z", "显示/隐藏悬浮字幕", "原 Ctrl+Alt+O 已取消"],
            ["Alt+F", "开启 / 关闭「解决黑屏」", "持续生效，考试中可用"],
            ["Alt+G", "立即还原「解决黑屏」", "交卷前按一下更稳"],
            ["↑ ↓ ← →", extras["arrows_effect"], extras["arrows_note"]],
        ],
        [5.0, 5.6, 6.2],
    )

    document.add_heading("七、注意事项（按重要性排序）", level=1)
    add_steps(
        document,
        [
            "只运行一个实例。重复双击会启动多个进程，只有第一个占住 8000 端口，手机可能连到旧版本，表现为「新功能没生效」。升级或重开前先在任务管理器结束所有 QQMusic 进程。",
            "「共享屏幕时隐藏控制台」默认不勾选。如果监考要求共享屏幕，先确认这条设置符合要求再开考；勾选后控制台不会出现在共享画面里，但手机端和字幕仍在工作。",
            "控制台不要随手最小化到托盘。最小化后热键仍生效，但你看不到状态；需要确认时从托盘图标恢复窗口。",
            "模型选择：不确定就先按默认（qwen 235B）。选到额度不足或不可用的模型，软件会自动切到可用路线并重试一次；连续失败时换一条路线再试。",
            "字幕透明度调到 0% 等于完全看不见，会以为软件坏了；建议 55%–75%。",
            "快捷键用轮询方式读取按键，不装键盘钩子：考试客户端以管理员权限运行、前台窗口不可钩时依然有效；"
            "如果某个键在某软件里被占用，换用另一个键即可。",
            "鼠标停在「模型」「秒数」「透明度」上滚轮只会滚动页面，不会改值；改值请点开下拉、用方向键或点上下箭头。",
            "「解决黑屏」只对覆盖截图区域的目标窗口解除保护，不动本软件窗口；开启后一直生效，退出或 Alt+G 才还原。",
            "截图修复只对 Windows 有效，且对「以管理员身份运行」的程序可能无效；遇到黑屏/透明窗口，右键用管理员身份运行本软件，或点「截图诊断」留报告。",
            "手机务必常亮并关闭省电模式；iOS 的低电量模式会断开后台网页连接。",
            "系统通知、微信/QQ 弹窗会遮挡题目并出现在截图里，开考前全部关闭或开启勿扰。",
            extras["chunk_tip"],
            "题库命中的答案是本地匹配，题干稍有差异可能匹配错，务必自己核对后再提交。",
            "交卷前：Alt+G 还原「解决黑屏」→ Alt+Z 关闭字幕 → 退出软件 → 确认手机页面已断开。",
            "不要把本软件、Key、截图发给无关的人；Key 泄露会被他人消耗额度。",
        ],
    )

    document.add_heading("八、常见问题", level=1)
    add_table(
        document,
        ["现象", "处理"],
        [
            ["双击没反应 / 一闪而过", "多为杀毒拦截。把所在目录加入信任区后重新解压运行"],
            ["手机打不开页面", "确认同一 WiFi、关闭 VPN、允许防火墙；重新点「复制网址」手动输入"],
            ["手机显示「等待电脑端发送题目」", "电脑端未截图或未连接；先在电脑上截一道题"],
            ["截图全黑 / 只有背景", "勾选「截图异常自动修复」；仍失败则以管理员身份运行，或点「截图诊断」"],
            ["按 Alt+Z 没反应", "确认软件在运行且未被安全软件拦截；v0.2.80 起改用轮询，重启软件再试"],
            ["解决黑屏没反应", "目标可能是受保护进程，日志里会写「目标受保护」；改用手机端看答案"],
            ["中键长按无效", "确认「自动截全屏」未被其他软件占用；中键按下保持满 1 秒再松开"],
            ["答案一直转圈", "Key 额度不足或网络不通；换模型路线，或检查代理"],
            ["字幕挡住题目", "拖动字幕到屏幕边缘，或把透明度调低"],
            ["升级后功能像没生效", "旧实例还占着端口；结束所有 QQMusic 进程后只开新版"],
        ],
        [5.6, 11.2],
    )

    document.add_heading("九、一页速查（可打印）", level=1)
    add_bullets(
        document,
        [
            "开考前：结束旧实例 → 开软件 → 填 Key 保存 → 手机扫码 → 关通知 → 接电源。",
            "单题：左键长按 2 秒 → 点终点 → 看手机答案。",
            "整屏：右键长按 2 秒；多图：连续截图 ×2–5 → 分析连续截图缓存。",
            "字幕：Alt+Z；透明度 55%–75%。",
            "黑屏：Alt+F 开启 / 关闭，Alt+G 还原。",
            "自动截屏：中键长按 1 秒 / 左键三连击。",
            extras["quick_arrow"],
            "交卷前：关字幕 → 退软件。",
        ],
    )

    document.add_paragraph()
    footer = document.add_paragraph()
    run = footer.add_run(f"AI 搜题助手 {version} · 本文档随安装包一起分发")
    set_east_asian(run)
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED

    path.parent.mkdir(parents=True, exist_ok=True)
    apply_disclaimer(document)
    document.save(path)


if __name__ == "__main__":
    desktop = Path.home() / "Desktop"
    build(
        desktop / "使用说明-v0.2.80.docx",
        version="v0.2.80",
        edition="主版本，16 条模型路线",
        routes="16 条：豆包 4 条、OpenRouter 6 条国产 + GPT-4o / GPT-4.1 / DeepSeek V4.1 / Claude Opus 5.5 / GPT-6 Luna、DeepSeek 官方 1 条",
        extras={
            "other_routes": "11 条（无 GPT-4o / GPT-4.1 / Claude / GPT-6 / DeepSeek V4.1）",
            "code_block": "支持：自动换行、字号、自动巡览、复制代码、分段复制",
            "other_code_block": "仅基础答案区（翻页 / 自动翻页 / 复制答案）",
            "remote_arrows": "支持（↑↓ 翻页、←→ 代码左右滚）",
            "other_remote": "不支持",
            "code_block_extra": True,
            "remote_arrows_detail": True,
            "arrows_effect": "遥控手机答案框（↑↓ 翻页、←→ 代码滚）",
            "arrows_note": "无需组合键，默认开启",
            "quick_arrow": "电脑方向键：↑↓ 翻手机答案、←→ 滚代码。",
            "chunk_note": "字数受限的答题框，可用手机端的「分段复制」分次粘贴（见 5.5）。",
            "chunk_tip": "答题框有字数上限时不要一次贴整段，用手机端「分段复制」按 200 字左右分次粘贴。",
        },
    )
    build(
        desktop / "使用说明-v0.2.70.docx",
        version="v0.2.70",
        edition="0.62 分支，11 条模型路线",
        routes="11 条：豆包 4 条、OpenRouter 6 条（Qwen 四条 + GLM + MiniMax）、DeepSeek 官方 1 条；没有 GPT 系列",
        extras={
            "other_routes": "16 条（含 Claude / GPT-6 / DeepSeek V4.1，主版本 v0.2.74）",
            "code_block": "基础答案区（翻页 / 自动翻页 / 复制答案 / 清空）",
            "other_code_block": "主版本额外支持代码换行、字号、自动巡览、分段复制",
            "remote_arrows": "不支持（用手机触屏滑动）",
            "other_remote": "主版本支持电脑方向键遥控",
            "code_block_extra": False,
            "remote_arrows_detail": False,
            "arrows_effect": "手机端 / 输入框内的正常光标移动",
            "arrows_note": "本版本不遥控手机",
            "quick_arrow": "手机看答案用触屏上下滑；代码太长时横滑代码块。",
            "chunk_note": "字数受限的答题框，先复制整段，再在答题框里按需要分段粘贴。",
            "chunk_tip": "答题框有字数上限时，先复制整段再手动分段粘贴。",
        },
    )
    print("done")
