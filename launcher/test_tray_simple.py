# -*- coding: utf-8-sig -*-
"""简单托盘测试：验证pystray在pythonw下能否正常显示"""
import sys
import time
import os
from pathlib import Path

TIANJI_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = TIANJI_ROOT / "logs" / "tray_test.log"

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}\n"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except:
        pass

def main():
    log(f"Python: {sys.executable}")
    log(f"PID: {os.getpid()}")

    try:
        import pystray
        log("pystray 导入成功")
    except ImportError as e:
        log(f"pystray 导入失败: {e}")
        return

    try:
        from PIL import Image, ImageDraw
        log("PIL 导入成功")
    except ImportError as e:
        log(f"PIL 导入失败: {e}")
        return

    # 创建图标
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((2, 2, 62, 62), fill=(72, 61, 139, 255), outline=(255, 215, 0, 255), width=2)
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("msyh.ttc", 32)
    except:
        font = ImageFont.load_default()
    draw.text((18, 10), "天", fill=(255, 255, 255, 255), font=font)
    log("图标创建成功")

    # 创建托盘
    menu = pystray.Menu(
        pystray.MenuItem("天机v9.1 托盘测试", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("显示通知", lambda icon, item: icon.notify("托盘测试通知", "天机v9.1")),
        pystray.MenuItem("退出", lambda icon, item: icon.stop()),
    )

    icon = pystray.Icon(
        name="tianji_test",
        icon=img,
        title="天机v9.1 测试",
        menu=menu,
    )

    log("即将显示托盘图标...")
    log("如果用户能在任务栏右下角看到紫色圆形'天'字图标，说明托盘功能正常")

    # 显示通知
    try:
        icon.visible = True
    except Exception as e:
        log(f"设置visible失败: {e}")

    def on_ready(icon):
        log("托盘图标已显示在任务栏")
        try:
            icon.notify("天机v9.1 托盘测试", "托盘图标已成功显示！")
        except Exception as e:
            log(f"通知失败: {e}")

    threading = __import__('threading')

    def run_tray():
        icon.run()

    t = threading.Thread(target=run_tray, daemon=True)
    t.start()

    time.sleep(3)
    log("3秒后托盘应该已经显示")
    log(f"托盘图标名称: {icon.name}")
    log(f"托盘标题: {icon.title}")
    log(f"托盘可见性: {icon.visible if hasattr(icon, 'visible') else 'unknown'}")

    # 保持运行30秒，让用户有时间看到
    log("保持运行30秒...")
    time.sleep(30)
    log("测试结束，退出托盘")
    icon.stop()

if __name__ == "__main__":
    main()
