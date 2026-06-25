# src/main.py
"""IPTV 智能管理 GUI 工具 - 程序入口"""

import sys
import traceback
from pathlib import Path

# 处理打包后的路径问题
if getattr(sys, 'frozen', False):
    # 打包后，_MEIPASS 指向临时解压目录
    base_path = Path(sys._MEIPASS)
else:
    # 开发环境，当前文件所在目录的父目录
    base_path = Path(__file__).parent.parent

# 将 base_path 添加到 sys.path，确保能导入 src 模块
if str(base_path) not in sys.path:
    sys.path.insert(0, str(base_path))


def main():
    try:
        # 调试：打印路径信息（写入文件便于查看）
        try:
            with open("path_debug.log", "w", encoding="utf-8") as f:
                f.write(f"base_path: {base_path}\n")
                f.write(f"sys.path: {sys.path}\n")
                f.write(f"frozen: {getattr(sys, 'frozen', False)}\n")
        except:
            pass

        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        from src.gui.main_window import IPTVMainWindow
        from src.utils.logger_handler import setup_gui_logging

        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)
        app.setApplicationName("IPTV 智能管理工具")
        app.setOrganizationName("IPTVCollector")

        setup_gui_logging()

        window = IPTVMainWindow()
        window.show()

        sys.exit(app.exec())

    except Exception as e:
        # 将错误写入 error.log 文件
        error_msg = traceback.format_exc()
        try:
            with open("error.log", "w", encoding="utf-8") as f:
                f.write(error_msg)
        except:
            pass

        print("=" * 60)
        print("程序启动失败！")
        print("错误信息已写入 error.log")
        print("=" * 60)
        print(error_msg)
        input("按 Enter 键退出...")
        sys.exit(1)


if __name__ == "__main__":
    main()
