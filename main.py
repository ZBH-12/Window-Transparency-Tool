import os
import sys
import time
import threading

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
    QListWidgetItem,
    QSpinBox
)

from PyQt6.QtGui import (
    QAction,
    QIcon
)

from PyQt6.QtCore import Qt

import win32gui
import win32con
import win32api


# =========================================
# 资源路径
# =========================================

def resource_path(relative_path):

    try:
        base_path = sys._MEIPASS

    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(
        base_path,
        relative_path
    )


# =========================================
# 透明管理器
# =========================================

class TransparencyManager:

    def __init__(self):

        self.alpha = 127

        self.changed_windows = set()

    def set_alpha(self, hwnd, alpha):

        if not win32gui.IsWindow(hwnd):
            return

        style = win32gui.GetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE
        )

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

    def restore_all(self):

        for hwnd in list(self.changed_windows):

            try:
                self.set_alpha(hwnd, 255)
            except:
                pass

        self.changed_windows.clear()

    def make_transparent(self, hwnd):

        try:

            self.set_alpha(
                hwnd,
                self.alpha
            )

            self.changed_windows.add(hwnd)

        except:
            pass

    def restore_window(self, hwnd):

        try:
            self.set_alpha(hwnd, 255)
        except:
            pass

        if hwnd in self.changed_windows:
            self.changed_windows.remove(hwnd)

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

    def enum_windows(self):

        result = []

        def callback(hwnd, _):

            if self.ignore_window(hwnd):
                return

            title = win32gui.GetWindowText(hwnd)

            result.append((hwnd, title))

        win32gui.EnumWindows(
            callback,
            None
        )

        return result


# =========================================
# 后台点击器
# =========================================

class AutoClicker:

    def __init__(self):

        self.running = False

        self.thread = None

        self.hwnd = None

        self.point = None

        self.interval = 60

    def set_target(
        self,
        hwnd,
        point
    ):

        self.hwnd = hwnd

        self.point = point

    def click_once(self):

        if not self.hwnd:
            return

        x, y = self.point

        lParam = win32api.MAKELONG(
            x,
            y
        )

        win32gui.PostMessage(
            self.hwnd,
            win32con.WM_MOUSEMOVE,
            0,
            lParam
        )

        win32gui.PostMessage(
            self.hwnd,
            win32con.WM_LBUTTONDOWN,
            win32con.MK_LBUTTON,
            lParam
        )

        win32gui.PostMessage(
            self.hwnd,
            win32con.WM_LBUTTONUP,
            0,
            lParam
        )

    def loop(self):

        while self.running:

            try:
                self.click_once()
            except:
                pass

            time.sleep(self.interval)

    def start(self):

        if self.running:
            return

        self.running = True

        self.thread = threading.Thread(
            target=self.loop,
            daemon=True
        )

        self.thread.start()

    def stop(self):

        self.running = False


# =========================================
# 主窗口
# =========================================

class MainWindow(QWidget):

    def __init__(self):

        super().__init__()

        self.manager = TransparencyManager()

        self.clicker = AutoClicker()

        self.target_hwnd = None

        self.target_point = None

        self.init_ui()

        self.init_tray()

        self.refresh_window_list()

    # =====================================
    # UI
    # =====================================

    def init_ui(self):

        self.setWindowTitle(
            "Window Tool"
        )

        self.setWindowIcon(
            QIcon(
                resource_path("icon.ico")
            )
        )

        self.resize(550, 800)

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
        """)

        layout = QVBoxLayout()

        title = QLabel(
            "窗口透明器 + 自动点击器"
        )

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        title.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
        """)

        layout.addWidget(title)

        # =========================
        # 透明度
        # =========================

        alpha_text = QLabel(
            "透明度"
        )

        alpha_text.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(alpha_text)

        self.slider = QSlider(
            Qt.Orientation.Horizontal
        )

        self.slider.setMinimum(0)

        self.slider.setMaximum(255)

        self.slider.setValue(127)

        self.slider.valueChanged.connect(
            self.change_alpha
        )

        layout.addWidget(self.slider)

        self.alpha_label = QLabel("127")

        self.alpha_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(self.alpha_label)

        # =========================
        # 刷新按钮
        # =========================

        self.refresh_button = QPushButton(
            "刷新窗口列表"
        )

        self.refresh_button.clicked.connect(
            self.refresh_window_list
        )

        layout.addWidget(
            self.refresh_button
        )

        # =========================
        # 窗口列表
        # =========================

        self.window_list = QListWidget()

        self.window_list.itemChanged.connect(
            self.handle_item_changed
        )

        layout.addWidget(self.window_list)

        # =========================
        # 自动点击
        # =========================

        click_title = QLabel(
            "后台自动点击"
        )

        click_title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        click_title.setStyleSheet("""
            font-size: 22px;
            font-weight: bold;
        """)

        layout.addWidget(click_title)

        self.target_label = QLabel(
            "当前目标：未选择"
        )

        self.target_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            self.target_label
        )

        self.select_button = QPushButton(
            "选择点击位置（按F8）"
        )

        self.select_button.clicked.connect(
            self.select_target
        )

        layout.addWidget(
            self.select_button
        )

        interval_layout = QHBoxLayout()

        interval_text = QLabel(
            "点击间隔（秒）"
        )

        interval_layout.addWidget(
            interval_text
        )

        self.interval_box = QSpinBox()

        self.interval_box.setMinimum(1)

        self.interval_box.setMaximum(
            999999
        )

        self.interval_box.setValue(60)

        interval_layout.addWidget(
            self.interval_box
        )

        layout.addLayout(
            interval_layout
        )

        click_button_layout = QHBoxLayout()

        self.start_click_button = QPushButton(
            "开始自动点击"
        )

        self.start_click_button.clicked.connect(
            self.start_clicking
        )

        self.stop_click_button = QPushButton(
            "停止自动点击"
        )

        self.stop_click_button.clicked.connect(
            self.stop_clicking
        )

        click_button_layout.addWidget(
            self.start_click_button
        )

        click_button_layout.addWidget(
            self.stop_click_button
        )

        layout.addLayout(
            click_button_layout
        )

        # =========================
        # 底部按钮
        # =========================

        bottom_layout = QHBoxLayout()

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

        bottom_layout.addWidget(
            self.restore_button
        )

        bottom_layout.addWidget(
            self.clear_button
        )

        layout.addLayout(
            bottom_layout
        )

        self.setLayout(layout)

    # =====================================
    # 托盘
    # =====================================

    def init_tray(self):

        self.tray = QSystemTrayIcon(self)

        self.tray.setIcon(
            QIcon(
                resource_path("icon.ico")
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

        quit_action = QAction(
            "退出",
            self
        )

        quit_action.triggered.connect(
            self.quit_app
        )

        menu.addAction(show_action)

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
    # 勾选透明
    # =====================================

    def handle_item_changed(self, item):

        hwnd = item.data(
            Qt.ItemDataRole.UserRole
        )

        if item.checkState() == Qt.CheckState.Checked:

            self.manager.make_transparent(
                hwnd
            )

        else:

            self.manager.restore_window(
                hwnd
            )

    # =====================================
    # 修改透明度
    # =====================================

    def change_alpha(self, value):

        self.manager.alpha = value

        self.alpha_label.setText(
            str(value)
        )

        for hwnd in self.manager.changed_windows:

            self.manager.set_alpha(
                hwnd,
                value
            )

    # =====================================
    # 选择目标
    # =====================================

    def select_target(self):

        QMessageBox.information(
            self,
            "提示",
            "请把鼠标移动到目标位置，然后按 F8"
        )

        threading.Thread(
            target=self.wait_f8,
            daemon=True
        ).start()

    def wait_f8(self):

        while True:

            if win32api.GetAsyncKeyState(
                win32con.VK_F8
            ) & 1:

                screen_point = (
                    win32gui.GetCursorPos()
                )

                hwnd = win32gui.WindowFromPoint(
                    screen_point
                )

                title = win32gui.GetWindowText(
                    hwnd
                )

                client_point = win32gui.ScreenToClient(
                    hwnd,
                    screen_point
                )

                self.target_hwnd = hwnd

                self.target_point = client_point

                self.clicker.set_target(
                    hwnd,
                    client_point
                )

                self.target_label.setText(
                    f"当前目标：{title} "
                    f"({client_point[0]}, "
                    f"{client_point[1]})"
                )

                break

            time.sleep(0.01)

    # =====================================
    # 开始点击
    # =====================================

    def start_clicking(self):

        if not self.target_hwnd:

            QMessageBox.warning(
                self,
                "错误",
                "请先选择目标"
            )

            return

        self.clicker.interval = (
            self.interval_box.value()
        )

        self.clicker.start()

        QMessageBox.information(
            self,
            "完成",
            "自动点击已启动"
        )

    # =====================================
    # 停止点击
    # =====================================

    def stop_clicking(self):

        self.clicker.stop()

        QMessageBox.information(
            self,
            "完成",
            "自动点击已停止"
        )

    # =====================================
    # 恢复窗口
    # =====================================

    def restore_windows(self):

        self.manager.restore_all()

        self.refresh_window_list()

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
            "Window Tool",
            "程序已最小化到托盘"
        )

    # =====================================
    # 退出
    # =====================================

    def quit_app(self):

        self.clicker.stop()

        self.manager.restore_all()

        QApplication.quit()


# =========================================
# 主程序
# =========================================

app = QApplication(sys.argv)

window = MainWindow()

window.show()

sys.exit(app.exec())