#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
天机v9.1 安装程序 (PyInstaller编译为.exe)
==========================================
功能: GUI安装向导, 选择目录, 解压文件, 创建快捷方式, 一键完成
"""

import os
import sys
import json
import shutil
import zipfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime

# 配置
APP_NAME = "天机v9.1"
APP_VERSION = "9.1.0"
DEFAULT_INSTALL_DIR = r"D:\天机v9.1"
PAYLOAD_DIR = "payload"  # 内嵌的发布包数据

# 获取exe所在目录(兼容PyInstaller打包)
if getattr(sys, 'frozen', False):
    EXE_DIR = Path(sys._MEIPASS)
else:
    EXE_DIR = Path(__file__).parent


class TianjiInstaller:
    """天机安装程序主界面"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} 安装向导")
        self.root.geometry("640x480")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        # 居中显示
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 640) // 2
        y = (self.root.winfo_screenheight() - 480) // 2
        self.root.geometry(f"640x480+{x}+{y}")

        self.install_dir = tk.StringVar(value=DEFAULT_INSTALL_DIR)
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="准备安装...")
        self.installing = False

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        bg = "#1a1a2e"
        fg = "#e0e0e0"
        accent = "#0f3460"
        highlight = "#e94560"

        # 标题
        title_frame = tk.Frame(self.root, bg=accent, height=80)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)

        tk.Label(
            title_frame, text=f"{APP_NAME}",
            font=("Microsoft YaHei", 22, "bold"),
            bg=accent, fg=highlight
        ).pack(pady=(12, 0))

        tk.Label(
            title_frame, text=f"AI智能记忆平台 v{APP_VERSION}",
            font=("Microsoft YaHei", 11),
            bg=accent, fg=fg
        ).pack()

        # 内容区
        content = tk.Frame(self.root, bg=bg, padx=30, pady=20)
        content.pack(fill="both", expand=True)

        # 安装目录
        tk.Label(
            content, text="安装目录:",
            font=("Microsoft YaHei", 10),
            bg=bg, fg=fg, anchor="w"
        ).pack(fill="x")

        dir_frame = tk.Frame(content, bg=bg)
        dir_frame.pack(fill="x", pady=(5, 15))

        dir_entry = tk.Entry(
            dir_frame, textvariable=self.install_dir,
            font=("Microsoft YaHei", 10),
            bg="#16213e", fg=fg, insertbackground=fg,
            relief="flat", bd=5
        )
        dir_entry.pack(side="left", fill="x", expand=True, ipady=4)

        tk.Button(
            dir_frame, text="浏览...", command=self._browse_dir,
            font=("Microsoft YaHei", 9),
            bg=accent, fg=fg, relief="flat",
            padx=15, pady=4, cursor="hand2"
        ).pack(side="right", padx=(10, 0))

        # 功能说明
        features = [
            "内置 Python 3.12 运行时, 无需预装任何软件",
            "核心引擎字节码保护, 商业级源码安全",
            "27+ MCP工具, 100+ API端点, 全量功能",
            "Tauri桌面应用 + Web界面双模式",
            "一键启动, 自动创建桌面图标",
        ]
        for feat in features:
            tk.Label(
                content, text=f"  {feat}",
                font=("Microsoft YaHei", 9),
                bg=bg, fg="#a0a0a0", anchor="w"
            ).pack(fill="x", pady=1)

        # 进度条
        self.progress = tk.Canvas(
            content, height=24, bg="#16213e",
            highlightthickness=0
        )
        self.progress.pack(fill="x", pady=(20, 5))

        # 状态文字
        tk.Label(
            content, textvariable=self.status_var,
            font=("Microsoft YaHei", 9),
            bg=bg, fg="#a0a0a0", anchor="w"
        ).pack(fill="x")

        # 底部按钮
        btn_frame = tk.Frame(self.root, bg=bg, padx=30, pady=15)
        btn_frame.pack(fill="x")

        self.install_btn = tk.Button(
            btn_frame, text="开始安装", command=self._start_install,
            font=("Microsoft YaHei", 11, "bold"),
            bg=highlight, fg="white", relief="flat",
            padx=30, pady=8, cursor="hand2"
        )
        self.install_btn.pack(side="right")

        tk.Button(
            btn_frame, text="取消", command=self._cancel,
            font=("Microsoft YaHei", 10),
            bg="#333", fg=fg, relief="flat",
            padx=20, pady=8, cursor="hand2"
        ).pack(side="right", padx=(0, 10))

    def _browse_dir(self):
        """选择安装目录"""
        d = filedialog.askdirectory(
            title="选择天机v9.1安装目录",
            initialdir=self.install_dir.get()
        )
        if d:
            self.install_dir.set(d)

    def _update_progress(self, value, status=""):
        """更新进度条"""
        self.progress_var.set(value)
        self.progress.delete("all")
        w = self.progress.winfo_width()
        h = self.progress.winfo_height()
        fill_w = int(w * value / 100)
        self.progress.create_rectangle(0, 0, fill_w, h, fill="#e94560", outline="")
        self.progress.create_rectangle(fill_w, 0, w, h, fill="#16213e", outline="")
        # 进度文字
        self.progress.create_text(
            w // 2, h // 2,
            text=f"{value:.0f}%",
            fill="white", font=("Microsoft YaHei", 9, "bold")
        )
        if status:
            self.status_var.set(status)
        self.root.update_idletasks()

    def _start_install(self):
        """开始安装"""
        if self.installing:
            return
        self.installing = True
        self.install_btn.config(state="disabled", text="安装中...")
        threading.Thread(target=self._do_install, daemon=True).start()

    def _do_install(self):
        """执行安装(后台线程)"""
        try:
            install_path = Path(self.install_dir.get())

            # Step 1: 检查/创建目录
            self.root.after(0, self._update_progress, 5, "准备安装目录...")
            install_path.mkdir(parents=True, exist_ok=True)

            # Step 2: 查找payload
            payload_path = EXE_DIR / PAYLOAD_DIR
            if not payload_path.exists():
                # 尝试查找同目录下的zip文件
                zip_candidates = list(EXE_DIR.glob("*.zip"))
                if zip_candidates:
                    payload_path = zip_candidates[0]
                else:
                    # 查找发布包目录
                    release_path = Path(r"D:\元初系统\天机v9.1\release\天机v9.1-全量发布包")
                    if release_path.exists():
                        payload_path = release_path
                    else:
                        self.root.after(0, lambda: messagebox.showerror(
                            "安装失败", "未找到安装数据!\n请确认安装包完整。"
                        ))
                        self._reset_ui()
                        return

            # Step 3: 复制文件
            if payload_path.is_dir():
                self._copy_dir(payload_path, install_path)
            elif str(payload_path).endswith(".zip"):
                self._extract_zip(payload_path, install_path)

            # Step 4: 创建桌面快捷方式
            self.root.after(0, self._update_progress, 95, "创建桌面快捷方式...")
            self._create_shortcuts(install_path)

            # Step 5: 写入版本信息
            version_info = {
                "product": "天机",
                "version": APP_VERSION,
                "build": int(datetime.now().strftime("%Y%m%d")) * 100 + 1,
                "release_date": datetime.now().strftime("%Y-%m-%d"),
                "install_dir": str(install_path),
                "channel": "stable",
            }
            version_file = install_path / "version.json"
            with open(version_file, "w", encoding="utf-8") as f:
                json.dump(version_info, f, ensure_ascii=False, indent=2)

            # 完成
            self.root.after(0, self._update_progress, 100, "安装完成!")
            self.root.after(0, self._install_done, install_path)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                "安装失败", f"安装过程中出错:\n{str(e)}"
            ))
            self._reset_ui()

    def _copy_dir(self, src: Path, dst: Path):
        """复制目录(带进度)"""
        # 先统计文件数
        all_files = []
        for f in src.rglob("*"):
            if f.is_file():
                rel = f.relative_to(src)
                # 跳过不需要的文件
                skip = False
                for part in rel.parts:
                    if part in ("__pycache__", ".git", "logs"):
                        skip = True
                        break
                if not skip:
                    all_files.append((f, rel))

        total = len(all_files)
        for i, (src_file, rel_path) in enumerate(all_files):
            dst_file = dst / rel_path
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_file), str(dst_file))

            pct = 5 + (i + 1) / total * 85
            status = f"复制文件: {rel_path.name} ({i+1}/{total})"
            self.root.after(0, self._update_progress, pct, status)

    def _extract_zip(self, zip_path: Path, dst: Path):
        """解压ZIP(带进度)"""
        with zipfile.ZipFile(str(zip_path), 'r') as zf:
            members = zf.infolist()
            total = len(members)
            for i, member in enumerate(members):
                zf.extract(member, str(dst))
                pct = 5 + (i + 1) / total * 85
                status = f"解压: {member.filename} ({i+1}/{total})"
                self.root.after(0, self._update_progress, pct, status)

    def _create_shortcuts(self, install_path: Path):
        """创建桌面快捷方式"""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            desktop = shell.SpecialFolders("Desktop")

            # 启动快捷方式
            lnk = shell.CreateShortCut(f"{desktop}\\{APP_NAME}.lnk")
            lnk.TargetPath = str(install_path / "启动天机.vbs")
            lnk.WorkingDirectory = str(install_path)
            tauri = install_path / "web" / "tianji.exe"
            if tauri.exists():
                lnk.IconLocation = f"{tauri},0"
            lnk.Description = f"{APP_NAME} AI智能记忆平台"
            lnk.Save()

            # 停止快捷方式
            lnk2 = shell.CreateShortCut(f"{desktop}\\停止天机.lnk")
            lnk2.TargetPath = str(install_path / "停止天机.vbs")
            lnk2.WorkingDirectory = str(install_path)
            if tauri.exists():
                lnk2.IconLocation = f"{tauri},0"
            lnk2.Description = "停止天机服务"
            lnk2.Save()
        except ImportError:
            # 无win32com, 用VBScript创建
            vbs = f'''
Set WshShell = CreateObject("WScript.Shell")
desktop = WshShell.SpecialFolders("Desktop")
Set lnk = WshShell.CreateShortcut(desktop & "\\{APP_NAME}.lnk")
lnk.TargetPath = "{install_path}\\启动天机.vbs"
lnk.WorkingDirectory = "{install_path}"
lnk.IconLocation = "{install_path}\\web\\tianji.exe,0"
lnk.Save
Set lnk2 = WshShell.CreateShortcut(desktop & "\\停止天机.lnk")
lnk2.TargetPath = "{install_path}\\停止天机.vbs"
lnk2.WorkingDirectory = "{install_path}"
lnk2.IconLocation = "{install_path}\\web\\tianji.exe,0"
lnk2.Save
'''
            vbs_file = install_path / "_create_shortcuts.vbs"
            with open(vbs_file, "w", encoding="gbk") as f:
                f.write(vbs)
            os.system(f'cscript //nologo "{vbs_file}"')
            vbs_file.unlink(missing_ok=True)

    def _install_done(self, install_path: Path):
        """安装完成"""
        result = messagebox.askyesno(
            "安装完成",
            f"{APP_NAME} v{APP_VERSION} 安装成功!\n\n"
            f"安装目录: {install_path}\n\n"
            f"是否立即启动天机?",
            icon=messagebox.INFO
        )
        if result:
            # 启动天机
            vbs = install_path / "启动天机.vbs"
            if vbs.exists():
                os.system(f'cscript //nologo "{vbs}"')
        self.root.destroy()

    def _reset_ui(self):
        """重置UI"""
        self.installing = False
        self.install_btn.config(state="normal", text="开始安装")

    def _cancel(self):
        """取消安装"""
        if self.installing:
            if not messagebox.askyesno("确认", "安装正在进行中, 确定取消?"):
                return
        self.root.destroy()

    def run(self):
        """运行安装程序"""
        self.root.mainloop()


if __name__ == "__main__":
    app = TianjiInstaller()
    app.run()
