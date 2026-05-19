import sys

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QHBoxLayout,
    QSystemTrayIcon,
    QMenu,
    QMessageBox,
    QListWidget,
    QListWidgetItem
)

from PyQt6.QtGui import QAction

from PyQt6.QtCore import Qt

import win32gui
import win32con


# =========================================
# 透明管理器
# =========================================

class TransparencyManager:

    def __init__(self):

        # 默认透明度改为 127
        self.alpha = 127

        # 已透明窗口
        self.changed_windows = set()

    # 设置窗口透明度
    def set_alpha(self, hwnd, alpha):

        if not win32gui.IsWindow(hwnd):
            return

        style = win32gui.GetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE
        )

        # 添加 WS_EX_LAYERED
        if not (style & win32con.WS_EX_LAYERED):

            win32gui.SetWindowLong(
                hwnd,
                win32con.GWL_EXSTYLE,
                style | win32con.WS_EX_LAYERED
            )

        win32gui.SetLayeredWindowAttributes(
            hwnd,
            0,
            alpha,
            win32con.LWA_ALPHA
        )

    # 恢复所有窗口
    def restore_all(self):

        for hwnd in list(self.changed_windows):

            try:
                self.set_alpha(hwnd, 255)

            except:
                pass

        self.changed_windows.clear()

    # 透明化窗口
    def make_transparent(self, hwnd):

        try:

            self.set_alpha(hwnd, self.alpha)

            self.changed_windows.add(hwnd)

        except:
            pass

    # 恢复窗口
    def restore_window(self, hwnd):

        try:

            self.set_alpha(hwnd, 255)

        except:
            pass

        if hwnd in self.changed_windows:
            self.changed_windows.remove(hwnd)

    # 是否忽略窗口
    def ignore_window(self, hwnd):

        if hwnd == 0:
            return True

        if hwnd == win32gui.GetDesktopWindow():
            return True

        if not win32gui.IsWindowVisible(hwnd):
            return True

        title = win32gui.GetWindowText(hwnd)

        if title.strip() == "":
            return True

        return False

    # 枚举窗口
    def enum_windows(self):

        result = []

        def callback(hwnd, _):

            if self.ignore_window(hwnd):
                return

            title = win32gui.GetWindowText(hwnd)

            result.append((hwnd, title))

        win32gui.EnumWindows(callback, None)

        return result


# =========================================
# 主窗口
# =========================================

class MainWindow(QWidget):

    def __init__(self):

        super().__init__()

        self.manager = TransparencyManager()

        self.init_ui()

        self.init_tray()

        self.refresh_window_list()

    # =====================================
    # UI
    # =====================================

    def init_ui(self):

        self.setWindowTitle(
            "Window Transparency Tool"
        )

        self.resize(500, 650)

        self.setStyleSheet("""
            QWidget {
                background-color: #202020;
                color: white;
                font-size: 14px;
            }

            QPushButton {
                background-color: #3a3a3a;
                border: none;
                border-radius: 10px;
                padding: 10px;
            }

            QPushButton:hover {
                background-color: #505050;
            }

            QListWidget {
                background-color: #2b2b2b;
                border-radius: 10px;
                padding: 5px;
            }

            QSlider::groove:horizontal {
                background: #444444;
                height: 8px;
                border-radius: 4px;
            }

            QSlider::handle:horizontal {
                background: #808080;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """)

        layout = QVBoxLayout()

        # 标题
        title = QLabel("窗口透明工具")

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        title.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
        """)

        layout.addWidget(title)

        # 透明度文字
        alpha_text = QLabel("透明度")

        alpha_text.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(alpha_text)

        # 滑块
        self.slider = QSlider(
            Qt.Orientation.Horizontal
        )

        # 下限 0
        self.slider.setMinimum(0)

        self.slider.setMaximum(255)

        # 默认值改为 127
        self.slider.setValue(127)

        self.slider.valueChanged.connect(
            self.change_alpha
        )

        layout.addWidget(self.slider)

        # 当前透明度显示
        self.alpha_label = QLabel("127")

        self.alpha_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(self.alpha_label)

        # 刷新按钮
        self.refresh_button = QPushButton(
            "刷新窗口列表"
        )

        self.refresh_button.clicked.connect(
            self.refresh_window_list
        )

        layout.addWidget(self.refresh_button)

        # 窗口列表
        self.window_list = QListWidget()

        self.window_list.itemChanged.connect(
            self.handle_item_changed
        )

        layout.addWidget(self.window_list)

        # 底部按钮
        button_layout = QHBoxLayout()

        self.restore_button = QPushButton(
            "恢复全部窗口"
        )

        self.restore_button.clicked.connect(
            self.restore_windows
        )

        self.clear_button = QPushButton(
            "清空列表"
        )

        self.clear_button.clicked.connect(
            self.clear_list
        )

        button_layout.addWidget(
            self.restore_button
        )

        button_layout.addWidget(
            self.clear_button
        )

        layout.addLayout(button_layout)

        # 提示
        info = QLabel(
            "勾选窗口即可透明化\n"
            "取消勾选即可恢复\n"
            "0 = 完全不可见"
        )

        info.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(info)

        self.setLayout(layout)

    # =====================================
    # 托盘
    # =====================================

    def init_tray(self):

        self.tray = QSystemTrayIcon(self)

        self.tray.setIcon(
            self.style().standardIcon(
                self.style().StandardPixmap.SP_ComputerIcon
            )
        )

        menu = QMenu()

        show_action = QAction(
            "显示窗口",
            self
        )

        show_action.triggered.connect(
            self.show
        )

        refresh_action = QAction(
            "刷新窗口列表",
            self
        )

        refresh_action.triggered.connect(
            self.refresh_window_list
        )

        restore_action = QAction(
            "恢复全部窗口",
            self
        )

        restore_action.triggered.connect(
            self.restore_windows
        )

        quit_action = QAction(
            "退出",
            self
        )

        quit_action.triggered.connect(
            self.quit_app
        )

        menu.addAction(show_action)
        menu.addAction(refresh_action)
        menu.addAction(restore_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)

        self.tray.show()

    # =====================================
    # 刷新窗口列表
    # =====================================

    def refresh_window_list(self):

        self.window_list.blockSignals(True)

        self.window_list.clear()

        windows = self.manager.enum_windows()

        for hwnd, title in windows:

            item = QListWidgetItem(title)

            item.setData(
                Qt.ItemDataRole.UserRole,
                hwnd
            )

            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
            )

            if hwnd in self.manager.changed_windows:

                item.setCheckState(
                    Qt.CheckState.Checked
                )

            else:

                item.setCheckState(
                    Qt.CheckState.Unchecked
                )

            self.window_list.addItem(item)

        self.window_list.blockSignals(False)

    # =====================================
    # 勾选事件
    # =====================================

    def handle_item_changed(self, item):

        hwnd = item.data(
            Qt.ItemDataRole.UserRole
        )

        if item.checkState() == Qt.CheckState.Checked:

            self.manager.make_transparent(hwnd)

        else:

            self.manager.restore_window(hwnd)

    # =====================================
    # 修改透明度
    # =====================================

    def change_alpha(self, value):

        self.manager.alpha = value

        self.alpha_label.setText(str(value))

        # 实时更新所有透明窗口
        for hwnd in self.manager.changed_windows:

            self.manager.set_alpha(hwnd, value)

    # =====================================
    # 恢复全部
    # =====================================

    def restore_windows(self):

        self.manager.restore_all()

        self.refresh_window_list()

        QMessageBox.information(
            self,
            "完成",
            "所有窗口已恢复"
        )

    # =====================================
    # 清空列表
    # =====================================

    def clear_list(self):

        self.window_list.clear()

    # =====================================
    # 最小化托盘
    # =====================================

    def closeEvent(self, event):

        event.ignore()

        self.hide()

        self.tray.showMessage(
            "窗口透明工具",
            "程序已最小化到托盘"
        )

    # =====================================
    # 退出
    # =====================================

    def quit_app(self):

        self.manager.restore_all()

        QApplication.quit()


# =========================================
# 主程序
# =========================================

app = QApplication(sys.argv)

window = MainWindow()

window.show()

sys.exit(app.exec())