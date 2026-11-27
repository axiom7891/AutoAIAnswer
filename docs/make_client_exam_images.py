"""生成「客户端考试使用教程」的配图。

图片：
1. console.png  —— 控制台真实界面（离屏渲染后截取）
2. hotkeys.png  —— 「查看所有热键」弹窗
3. subtitle.png —— 考试客户端 + 悬浮字幕示意
4. phone.png    —— 手机端答案页示意
5. flow.png     —— 考前 / 考中 / 交卷 三步流程
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\\Windows\\Fonts")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent / "assets_client_exam"
OUT.mkdir(parents=True, exist_ok=True)

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"


def grab_widgets() -> None:
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication, QDialog, QTextBrowser

    from ai_screenshot_assistant.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    for font_file in (r"C:\\Windows\\Fonts\\msyh.ttc", r"C:\\Windows\\Fonts\\msyhbd.ttc", r"C:\\Windows\\Fonts\\simhei.ttf"):
        QFontDatabase.addApplicationFont(font_file)
    app.setFont(QFont("Microsoft YaHei", 10))
    window = MainWindow()
    # 截图前把 Key 打码，避免文档里泄露真实密钥
    for field_name in ("deepseek_key_input", "openrouter_key_input", "doubao_key_input"):
        field = getattr(window, field_name, None)
        if field is not None:
            field.setText("sk-************************")
    window.resize(1080, 1500)
    window.show()
    for _ in range(30):
        app.processEvents()

    # 滚到「截图与手势」卡片附近再截
    area = window.centralWidget()
    area.verticalScrollBar().setValue(420)
    for _ in range(20):
        app.processEvents()
    window.grab().save(str(OUT / "console.png"))

    def grab_dialog() -> None:
        for widget in app.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                widget.grab().save(str(OUT / "hotkeys.png"))
                if widget.findChildren(QTextBrowser):
                    widget.accept()

    QTimer.singleShot(700, grab_dialog)
    window._show_hotkey_help()
    window.close()


def draw_subtitle() -> None:
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1600, 900
    image = Image.new("RGB", (width, height), "#f5f6f8")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(FONT_BOLD, 30)
    body_font = ImageFont.truetype(FONT_PATH, 24)
    small_font = ImageFont.truetype(FONT_PATH, 20)

    # 模拟考试客户端
    draw.rectangle([0, 0, width, 64], fill="#1f2937")
    draw.text((28, 16), "在线笔试客户端  ·  第 12 题 / 40", font=small_font, fill="#e5e7eb")
    draw.text((width - 240, 16), "剩余 46:12", font=small_font, fill="#fca5a5")

    draw.text((60, 110), "12. 下列关于 TCP 拥塞控制的说法，正确的是：", font=title_font, fill="#111827")
    options = [
        "A. 慢启动阶段拥塞窗口按指数增长，每经过一个 RTT 翻一倍",
        "B. 拥塞避免阶段拥塞窗口在每个 RTT 线性加一",
        "C. 快重传要求收到三个重复 ACK 后立即重传丢失报文",
        "D. 以上说法都正确",
    ]
    y = 190
    for option in options:
        draw.text((90, y), option, font=body_font, fill="#374151")
        y += 64

    # 悬浮字幕（半透明条）
    strip = Image.new("RGBA", (width - 120, 150), (17, 24, 39, 180))
    sdraw = ImageDraw.Draw(strip)
    sdraw.text((28, 22), "答案：D", font=ImageFont.truetype(FONT_BOLD, 34), fill="#ffffff")
    sdraw.text(
        (28, 78),
        "慢启动指数增长、拥塞避免线性增长、三个重复 ACK 触发快重传，三项均正确。",
        font=small_font,
        fill="#d1d5db",
    )
    image.paste(strip, (60, height - 210), strip)

    # 标注
    draw.rectangle([60, height - 210, width - 60, height - 60], outline="#10b981", width=3)
    draw.text((72, height - 250), "悬浮字幕：共享屏幕/录屏看不到（透明度建议 55%–75%）", font=small_font, fill="#059669")

    # 手机示意
    phone_x, phone_y = width - 330, 120
    draw.rounded_rectangle([phone_x, phone_y, phone_x + 270, phone_y + 380], radius=28, fill="#111827")
    draw.rounded_rectangle([phone_x + 12, phone_y + 12, phone_x + 258, phone_y + 368], radius=22, fill="#ffffff")
    draw.text((phone_x + 34, phone_y + 34), "AI 答案", font=small_font, fill="#6b7280")
    draw.text((phone_x + 34, phone_y + 84), "D", font=ImageFont.truetype(FONT_BOLD, 64), fill="#059669")
    draw.multiline_text(
        (phone_x + 34, phone_y + 180),
        "慢启动指数增长\n拥塞避免线性\n三重复 ACK 快重传",
        font=small_font,
        fill="#374151",
        spacing=8,
    )
    draw.rounded_rectangle(
        [phone_x + 30, phone_y + 300, phone_x + 240, phone_y + 344], radius=12, fill="#10b981"
    )
    draw.text((phone_x + 92, phone_y + 310), "复制答案", font=small_font, fill="#ffffff")

    image.save(OUT / "subtitle.png")


def draw_phone() -> None:
    from PIL import Image, ImageDraw, ImageFont

    width, height = 900, 1200
    image = Image.new("RGB", (width, height), "#eef2f5")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT_PATH, 26)
    bold = ImageFont.truetype(FONT_BOLD, 34)

    draw.rounded_rectangle([120, 40, 780, 1160], radius=44, fill="#0f172a")
    draw.rounded_rectangle([140, 60, 760, 1140], radius=36, fill="#ffffff")

    draw.text((175, 90), "● 已连接电脑  ·  8000", font=font, fill="#10b981")
    draw.text((175, 150), "第 12 题 · 单选", font=bold, fill="#111827")

    draw.rounded_rectangle([170, 210, 730, 620], radius=16, fill="#f8fafc", outline="#e2e8f0", width=2)
    draw.text((195, 235), "答案：D", font=bold, fill="#059669")
    draw.multiline_text(
        (195, 300),
        "慢启动：窗口按指数增长\n拥塞避免：每 RTT 线性 +1\n快重传：三个重复 ACK 立即重传\n\n三项描述都正确，选 D。",
        font=font,
        fill="#334155",
        spacing=10,
    )

    buttons = ["截全屏", "上一页", "下一页", "复制答案"]
    bx = 175
    for index, label in enumerate(buttons):
        color = "#10b981" if index == 0 else "#e2e8f0"
        text_color = "#ffffff" if index == 0 else "#334155"
        draw.rounded_rectangle([bx, 660, bx + 128, 720], radius=12, fill=color)
        draw.text((bx + 20, 678), label, font=ImageFont.truetype(FONT_PATH, 23), fill=text_color)
        bx += 142

    draw.text((175, 780), "系统 Prompt / 补充要求", font=font, fill="#64748b")
    draw.rounded_rectangle([170, 820, 730, 900], radius=12, fill="#f1f5f9")
    draw.text((195, 845), "只要答案，不要解析", font=font, fill="#94a3b8")

    draw.rounded_rectangle([170, 930, 730, 990], radius=12, fill="#10b981")
    draw.text((380, 945), "发送", font=bold, fill="#ffffff")

    image.save(OUT / "phone.png")


def draw_flow() -> None:
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1600, 520
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    title = ImageFont.truetype(FONT_BOLD, 34)
    body = ImageFont.truetype(FONT_PATH, 24)
    small = ImageFont.truetype(FONT_PATH, 21)

    steps = [
        ("考前 10 分钟", [
            "只开一个实例（结束旧进程）",
            "填 Key、选模型、导入题库",
            "手机连同一 WiFi 打开页面",
            "开「解决黑屏」，字幕调 55%–75%",
        ]),
        ("考试中", [
            "左键双击 / 右键长按 2 秒 取题",
            "字幕看答案，手机看详细解析",
            "Alt+Z 临时藏字幕",
            "Alt+F / Alt+G 切换黑屏修复",
        ]),
        ("交卷前后", [
            "Alt+G 还原黑屏修复",
            "Alt+Z 关闭字幕",
            "退出软件，手机断开",
            "确认没有残留窗口",
        ]),
    ]

    box_w, gap = 460, 80
    x = 40
    for index, (head, items) in enumerate(steps):
        draw.rounded_rectangle([x, 90, x + box_w, 430], radius=22, fill="#f8fafc", outline="#cbd5e1", width=2)
        draw.ellipse([x + 28, 60, x + 92, 124], fill="#10b981")
        draw.text((x + 48, 74), str(index + 1), font=title, fill="#ffffff")
        draw.text((x + 110, 74), head, font=title, fill="#0f172a")
        y = 170
        for item in items:
            draw.text((x + 32, y), "·", font=body, fill="#10b981")
            draw.text((x + 58, y), item, font=small, fill="#334155")
            y += 56
        if index < 2:
            draw.line([x + box_w + 10, 260, x + box_w + gap - 16, 260], fill="#94a3b8", width=4)
            draw.polygon(
                [(x + box_w + gap - 16, 260), (x + box_w + gap - 34, 248), (x + box_w + gap - 34, 272)],
                fill="#94a3b8",
            )
        x += box_w + gap

    image.save(OUT / "flow.png")


def main() -> None:
    grab_widgets()
    draw_subtitle()
    draw_phone()
    draw_flow()
    for path in sorted(OUT.glob("*.png")):
        print(path.name, path.stat().st_size)


if __name__ == "__main__":
    main()
