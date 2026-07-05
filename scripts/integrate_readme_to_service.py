"""
天机服务集成README自动化系统
将README自动化系统集成到tianji_service.py
"""

# 在tianji_service.py中添加以下代码:

"""
# 1. 导入模块
from core.shared.readme_auto_system import READMEAutoSystem, create_default_config

# 2. 在TianjiService类中添加属性
class TianjiService:
    def __init__(self):
        ...
        self._readme_auto = None  # README自动化系统

# 3. 在start()方法中启动README自动化
def start(self):
    ...
    # 启动README自动化系统
    try:
        readme_config = create_default_config(self._project_root)
        self._readme_auto = READMEAutoSystem(
            engine=self._engine,
            config=readme_config
        )
        config_file = Path(self._project_root) / "config" / "readme_auto_config.json"
        self._readme_auto.initialize(str(config_file))
        print("[天机服务] README自动化系统启动成功")
    except Exception as e:
        print(f"[天机服务] README自动化系统启动失败: {e}")

# 4. 在stop()方法中关闭README自动化
def stop(self):
    ...
    # 关闭README自动化系统
    if self._readme_auto:
        self._readme_auto.shutdown()
        self._readme_auto = None

# 5. 在托盘菜单中添加控制项
def _create_tray_menu(self):
    ...
    # README自动化控制
    menu.append(MenuItem("README自动化: 状态", self._show_readme_auto_status))
    menu.append(MenuItem("README自动化: 暂停", self._pause_readme_auto))
    menu.append(MenuItem("README自动化: 恢复", self._resume_readme_auto))
    menu.append(MenuItem("README自动化: 立即更新", self._trigger_readme_update))

# 6. 添加托盘菜单回调
def _show_readme_auto_status(self):
    if self._readme_auto:
        stats = self._readme_auto.get_stats()
        messagebox.showinfo(
            "README自动化状态",
            f"运行状态: {'运行中' if stats['running'] else '已停止'}\n"
            f"监控目录: {stats['watch_dirs']}\n"
            f"总更新次数: {stats['update_count']}\n"
            f"watchdog可用: {'是' if stats['watchdog_available'] else '否'}"
        )

def _pause_readme_auto(self):
    if self._readme_auto:
        self._readme_auto._config.trigger_config.enabled = False
        print("[天机服务] README自动化已暂停")

def _resume_readme_auto(self):
    if self._readme_auto:
        self._readme_auto._config.trigger_config.enabled = True
        print("[天机服务] README自动化已恢复")

def _trigger_readme_update(self):
    if self._readme_auto:
        from core.shared.readme_auto_system import AutoTriggerType
        for watch_dir in self._readme_auto._config.watch_dirs:
            self._readme_auto.trigger_update(watch_dir, AutoTriggerType.MANUAL)
        print("[天机服务] README手动更新触发成功")
"""

# 完整集成示例
INTEGRATION_CODE = """
# tianji_service.py 集成代码片段

# === 导入 ===
from core.shared.readme_auto_system import READMEAutoSystem, create_default_config, AutoTriggerType

# === TianjiService类扩展 ===
class TianjiService:
    def __init__(self):
        # ... 原有代码 ...
        self._readme_auto = None

    def start(self):
        # ... 原有代码 ...

        # 启动README自动化系统
        try:
            readme_config = create_default_config(str(self._project_root))
            self._readme_auto = READMEAutoSystem(
                engine=self._engine,
                config=readme_config
            )
            config_file = self._project_root / "config" / "readme_auto_config.json"
            self._readme_auto.initialize(str(config_file))
            logger.info("[README自动化] 启动成功")
        except Exception as e:
            logger.error(f"[README自动化] 启动失败: {e}")

    def stop(self):
        # ... 原有代码 ...

        # 关闭README自动化系统
        if self._readme_auto:
            self._readme_auto.shutdown()
            self._readme_auto = None

    # === 托盘菜单扩展 ===
    def _create_tray_menu(self):
        items = []

        # ... 原有菜单项 ...

        # README自动化菜单
        items.append(MenuItem("─" * 20, lambda: None))
        items.append(MenuItem("📝 README自动化", self._show_readme_auto_status))
        items.append(MenuItem("⏸ 暂停README自动化", self._pause_readme_auto))
        items.append(MenuItem("▶ 恢复README自动化", self._resume_readme_auto))
        items.append(MenuItem("🔄 立即更新README", self._trigger_readme_update))

        return items

    def _show_readme_auto_status(self):
        if not self._readme_auto:
            messagebox.showinfo("提示", "README自动化系统未启动")
            return

        stats = self._readme_auto.get_stats()
        status_text = f"""
运行状态: {'✅ 运行中' if stats['running'] else '❌ 已停止'}
监控目录: {stats['watch_dirs']}个
总更新次数: {stats['update_count']}
watchdog可用: {'✅ 是' if stats['watchdog_available'] else '❌ 否'}
防抖时间: {stats['config']['trigger_config']['debounce_seconds']}s
批处理大小: {stats['config']['trigger_config']['batch_size']}
周期更新间隔: {stats['config']['update_interval']}s
        """
        messagebox.showinfo("README自动化状态", status_text)

    def _pause_readme_auto(self):
        if self._readme_auto:
            self._readme_auto._config.trigger_config.enabled = False
            logger.info("[README自动化] 已暂停")

    def _resume_readme_auto(self):
        if self._readme_auto:
            self._readme_auto._config.trigger_config.enabled = True
            logger.info("[README自动化] 已恢复")

    def _trigger_readme_update(self):
        if not self._readme_auto:
            messagebox.showwarning("警告", "README自动化系统未启动")
            return

        for watch_dir in self._readme_auto._config.watch_dirs:
            self._readme_auto.trigger_update(watch_dir, AutoTriggerType.MANUAL)

        logger.info("[README自动化] 手动更新触发成功")
        messagebox.showinfo("提示", "README手动更新已触发")
"""

if __name__ == "__main__":
    print("=" * 60)
    print("天机服务README自动化集成指南")
    print("=" * 60)
    print("\n将以下代码集成到 tianji_service.py:")
    print("-" * 60)
    print(INTEGRATION_CODE)
    print("-" * 60)
