import keyboard
import tkinter as tk
from tkinter import messagebox, colorchooser, font as tkfont
import threading
import pystray
from PIL import Image, ImageDraw
import os
import sys
import json
import winreg
import ctypes
import time
import subprocess
import copy
import re
import shutil
import fnmatch
import queue

import customtkinter as ctk

from preset_library import PRESET_LIBRARY, PRESET_ORDER


# 版本历史：
#   1.1.3  初版（用户原始脚本）
#   1.1.4  修复按键录制/设置/开机自启/编码崩溃，支持打包 exe
#   1.2.0  新增软件预设库、自动模式、拖拽定位、CustomTkinter 现代界面
#   1.2.1  修复拖拽与 DPI 坐标错乱，新增自定义提示框大小
#   1.2.2  坐标全面物理化重写，修复字号缩放/监听稳定性/窗口焦点与 Alt-Tab，
#          新增“关于”页，版本化命名
#   1.2.3  钩子失效自愈（任务管理器等导致低级钩子被系统卸载）、首次运行自动
#          启用开机自启、自动模式默认关闭并增加免责声明；版本后缀改为 -beta
#   1.3.0  监听架构重写（原始键事件流+主线程轮询，钩子回调极轻量，根治
#          任务管理器/后台导致的钩子超时卸载）；新增持续输出模式；设置界面
#          性能优化；托盘新增重启程序、固定测试提示；自动模式不跨会话记忆
#   1.3.1  修复重启程序（释放单实例互斥）、任务管理器监听失效（真实按键
#          状态匹配+定期校准+轮询兜底）、设置界面展开字号/滚动、单实例
#          误判（GetLastError 陈旧值）
#   1.3.2  持续输出模式状态自愈（任务管理器过滤后自动校准）、预设展开字号
#          DPI 缩放修复、任务管理器首次运行提示与系统页常驻说明
VERSION = "1.3.2"

ctk.set_appearance_mode("dark")

APP_NAME = f"快捷键提示-{VERSION}-beta"
AUTOSTART_NAME = "ShortcutNotifier"
AUTOSTART_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

MOD_ORDER = {'ctrl': 0, 'alt': 1, 'shift': 2, 'win': 3}

RAW_KEY_MAP = {
    'left ctrl': 'ctrl', 'right ctrl': 'ctrl',
    'left shift': 'shift', 'right shift': 'shift',
    'left alt': 'alt', 'right alt': 'alt',
    'left windows': 'win', 'right windows': 'win',
    'delete': 'del',
    'menu': 'apps', 'apps': 'apps',
    'page up': 'page up', 'page down': 'page down',
    'print screen': 'print screen',
    # insert 保持 'insert'（与预设库键名一致）
}

MOD_VK = {'ctrl': 0x11, 'shift': 0x10, 'alt': 0x12, 'win': 0x5B}

VK_MAP = {
    'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45, 'f': 0x46,
    'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A, 'k': 0x4B, 'l': 0x4C,
    'm': 0x4D, 'n': 0x4E, 'o': 0x4F, 'p': 0x50, 'q': 0x51, 'r': 0x52,
    's': 0x53, 't': 0x54, 'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58,
    'y': 0x59, 'z': 0x5A,
    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73, 'f5': 0x74,
    'f6': 0x75, 'f7': 0x76, 'f8': 0x77, 'f9': 0x78, 'f10': 0x79,
    'f11': 0x7A, 'f12': 0x7B,
    'space': 0x20, 'enter': 0x0D, 'tab': 0x09, 'backspace': 0x08,
    'esc': 0x1B, 'caps lock': 0x14,
    'page up': 0x21, 'page down': 0x22, 'home': 0x24, 'end': 0x23,
    'ins': 0x2D, 'insert': 0x2D, 'del': 0x2E, 'delete': 0x2E,
    'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
    'print screen': 0x2C, 'num lock': 0x90, 'scroll lock': 0x91,
    'apps': 0x5D,
    ';': 0xBA, "'": 0xDE, ',': 0xBC, '-': 0xBD, '.': 0xBE,
    '/': 0xBF, '`': 0xC0, '[': 0xDB, '\\': 0xDC, ']': 0xDD, '=': 0xBB,
}

POSITIONS = ['bottom-center', 'bottom-right', 'bottom-left',
             'top-center', 'top-right', 'top-left', 'center', 'custom']

KEY_NAME_MAP = {
    'left ctrl': 'ctrl', 'right ctrl': 'ctrl',
    'left shift': 'shift', 'right shift': 'shift',
    'left alt': 'alt', 'right alt': 'alt',
    'left windows': 'win', 'right windows': 'win',
    'space': 'space', 'enter': 'enter', 'backspace': 'backspace',
    'delete': 'del', 'caps lock': 'caps lock', 'tab': 'tab', 'esc': 'esc',
    'print screen': 'print screen', 'insert': 'ins',
    'home': 'home', 'end': 'end',
    'num lock': 'num lock', 'scroll lock': 'scroll lock',
    'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right',
    'menu': 'apps', 'apps': 'apps',
}

DISPLAY_NAME_MAP = {
    'ctrl': 'Ctrl', 'shift': 'Shift', 'alt': 'Alt', 'win': 'Win',
    'del': 'Delete', 'page up': 'Page Up', 'page down': 'Page Down',
    'caps lock': 'Caps Lock', 'esc': 'Esc', 'enter': 'Enter',
    'backspace': 'Backspace', 'tab': 'Tab', 'space': 'Space',
    'ins': 'Insert', 'home': 'Home', 'end': 'End',
    'print screen': 'Print Screen', 'num lock': 'Num Lock',
    'scroll lock': 'Scroll Lock', 'apps': 'Menu',
}

_SINGLE_INSTANCE_MUTEX = None


def safe_log(msg):
    """把运行日志写入 AppData，避免控制台编码问题导致崩溃"""
    try:
        log_dir = os.path.join(
            os.environ.get('APPDATA') or os.path.dirname(os.path.abspath(__file__)),
            'ShortcutNotifier')
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, 'shortcut_notifier.log'),
                  'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def ensure_single_instance():
    """单实例互斥，防止重复启动两个监听"""
    global _SINGLE_INSTANCE_MUTEX
    try:
        # 先清零错误码，避免成功调用后 GetLastError 返回旧值导致误判
        ctypes.windll.kernel32.SetLastError(0)
        _SINGLE_INSTANCE_MUTEX = ctypes.windll.kernel32.CreateMutexW(
            None, False, "ShortcutNotifierSingleInstance")
        return ctypes.windll.kernel32.GetLastError() != 183
    except Exception:
        return True


def release_single_instance_mutex():
    """释放单实例互斥（重启程序前必须先释放，否则新进程会被判为重复实例）"""
    global _SINGLE_INSTANCE_MUTEX
    try:
        if _SINGLE_INSTANCE_MUTEX:
            ctypes.windll.kernel32.CloseHandle(_SINGLE_INSTANCE_MUTEX)
    except Exception:
        pass
    _SINGLE_INSTANCE_MUTEX = None


def rounded_rect_points(width, height, radius, border_width=0):
    """生成圆角矩形点集，border_width>0 时向外扩一圈作为描边"""
    x1, y1 = 1 - border_width, 1 - border_width
    x2, y2 = width - 2 + border_width, height - 2 + border_width
    r = max(radius, 0)
    return [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]


def offset_points(points, dx, dy):
    """把坐标点集整体平移 (dx, dy)"""
    return [points[i] + (dx if i % 2 == 0 else dy)
            for i in range(len(points))]


def is_valid_color(value):
    return bool(re.fullmatch(r'#[0-9a-fA-F]{6}', value or ''))


def get_foreground_window_info():
    """获取当前前台窗口的程序名与标题（用于自动模式）"""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return '', ''
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title_buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buf, 512)
        title = title_buf.value or ''
        exe = ''
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if handle:
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = ctypes.c_ulong(1024)
                if kernel32.QueryFullProcessImageNameW(
                        handle, 0, buf, ctypes.byref(size)):
                    exe = os.path.basename(buf.value)
            finally:
                kernel32.CloseHandle(handle)
        return exe, title
    except Exception:
        return '', ''


def preset_matches(preset, exe_name, title):
    """判断预设是否匹配当前前台软件"""
    exe_l = (exe_name or '').lower()
    title_l = (title or '').lower()
    for pattern in preset.get('apps', []):
        if pattern and fnmatch.fnmatch(exe_l, pattern.lower()):
            return True
    for keyword in preset.get('title_keywords', []):
        if keyword and keyword.lower() in title_l:
            return True
    return False


SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
MONITOR_DEFAULTTONEAREST = 2


def get_virtual_screen_bounds():
    """返回虚拟桌面范围 (left, top, right, bottom)，支持多显示器；失败返回 None"""
    try:
        user32 = ctypes.windll.user32
        left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        return left, top, left + width, top + height
    except Exception:
        return None


def get_work_area_at_cursor():
    """返回鼠标所在显示器的工作区 (left, top, right, bottom)，排除任务栏；失败返回 None"""
    try:
        user32 = ctypes.windll.user32

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                        ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

        point = POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return None
        monitor = user32.MonitorFromPoint(point, MONITOR_DEFAULTTONEAREST)
        if not monitor:
            return None
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            work = info.rcWork
            return work.left, work.top, work.right, work.bottom
    except Exception:
        pass
    return None


def get_cursor_pos():
    """获取鼠标指针的物理屏幕坐标 (x, y)，失败返回 None"""
    try:
        user32 = ctypes.windll.user32

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        point = POINT()
        if user32.GetCursorPos(ctypes.byref(point)):
            return point.x, point.y
    except Exception:
        pass
    return None


def get_last_input_wall_time():
    """系统最近一次输入（键鼠）对应的 wall-clock 时间，失败返回 None"""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if user32.GetLastInputInfo(ctypes.byref(info)):
            tick_now = kernel32.GetTickCount()
            elapsed = (tick_now - info.dwTime) & 0xFFFFFFFF
            return time.time() - elapsed / 1000.0
    except Exception:
        pass
    return None


def is_foreground_elevated():
    """前台窗口是否以管理员权限运行（用于区分钩子失效与 UIPI 权限过滤）"""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        advapi32 = ctypes.windll.advapi32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return False
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return False
        try:
            TOKEN_QUERY = 0x0008
            TokenElevation = 20
            token = ctypes.c_void_p()
            if not advapi32.OpenProcessToken(
                    handle, TOKEN_QUERY, ctypes.byref(token)):
                return False
            try:
                class TOKEN_ELEVATION(ctypes.Structure):
                    _fields_ = [("TokenIsElevated", ctypes.c_ulong)]
                elev = TOKEN_ELEVATION()
                size = ctypes.c_ulong(0)
                advapi32.GetTokenInformation(
                    token, TokenElevation, ctypes.byref(elev),
                    ctypes.sizeof(elev), ctypes.byref(size))
                return bool(elev.TokenIsElevated)
            finally:
                kernel32.CloseHandle(token)
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return False


class ForegroundWatcher(threading.Thread):
    """轮询前台窗口，自动模式下切换对应预设"""

    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app

    def run(self):
        while True:
            try:
                if self.app.settings.get('auto_mode'):
                    exe, title = get_foreground_window_info()
                    matched = {
                        pid for pid, preset in PRESET_LIBRARY.items()
                        if preset_matches(preset, exe, title)
                    }
                    self.app.on_foreground_matched(matched)
            except Exception:
                pass
            time.sleep(1)


class Settings:
    """设置管理类"""

    def __init__(self):
        self.settings_file = self.get_settings_path()
        self.settings = self.load_settings()

    def get_settings_path(self):
        """获取设置文件路径：打包后放在 AppData，便于移动 exe 位置"""
        if getattr(sys, 'frozen', False):
            base = os.path.join(
                os.environ.get('APPDATA') or os.path.expanduser('~'),
                'ShortcutNotifier')
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, 'shortcut_settings.json')

    def load_settings(self, use_file=True):
        """加载设置（含旧版数据迁移与容错）"""
        default_settings = {
            'settings_version': 1,
            'shortcuts': {},
            'preset_states': {
                pid: {'enabled': pid == 'windows', 'shortcuts': {}}
                for pid in PRESET_ORDER
            },
            'auto_mode': False,
            'autostart': True,
            'continuous_mode': False,
            'taskmgr_notice_shown': False,
            'appearance': {
                'window_opacity': 0.75,
                'display_duration': 1500,
                'fade_duration': 500,
                'position': 'bottom-center',
                'custom_position': None,
                'width_override': 0,
                'height_override': 0,
                'bg_color': '#2D2B3E',
                'text_color': '#FFFFFF',
                'border_color': '#FFFFFF',
                'font_size': 14,
            },
        }

        loaded = {}
        if use_file and os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
            except Exception as e:
                safe_log(f"设置文件读取失败，使用默认设置: {e}")
        elif use_file and getattr(sys, 'frozen', False):
            # 打包版首次运行：若 exe 旁边有旧设置文件则迁移到 AppData
            legacy = os.path.join(
                os.path.dirname(sys.executable), 'shortcut_settings.json')
            if os.path.exists(legacy):
                try:
                    os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
                    shutil.copy2(legacy, self.settings_file)
                    with open(self.settings_file, 'r', encoding='utf-8') as f:
                        loaded = json.load(f)
                except Exception as e:
                    safe_log(f"旧设置迁移失败: {e}")

        if isinstance(loaded, dict):
            for key, default_val in default_settings.items():
                if key not in loaded or loaded[key] is None:
                    continue
                if isinstance(default_val, dict) and isinstance(loaded[key], dict):
                    default_val.update({
                        k: v for k, v in loaded[key].items() if v is not None
                    })
                else:
                    default_settings[key] = loaded[key]

        # 自动模式为会话级设置：每次启动都强制关闭，不记忆上次状态
        default_settings['auto_mode'] = False
        default_settings.setdefault('continuous_mode', False)

        # 确保预设库中的每个预设都有状态
        for pid in PRESET_ORDER:
            state = default_settings['preset_states'].setdefault(
                pid, {'enabled': pid == 'windows', 'shortcuts': {}})
            if not isinstance(state, dict):
                state = default_settings['preset_states'][pid] = {
                    'enabled': pid == 'windows', 'shortcuts': {}}
            state.setdefault('enabled', pid == 'windows')
            state.setdefault('shortcuts', {})

        # 规范化用户自定义快捷键条目
        for shortcut, cfg in list(default_settings['shortcuts'].items()):
            if not isinstance(cfg, dict):
                default_settings['shortcuts'][shortcut] = {
                    'enabled': True, 'display': shortcut.upper()}
            else:
                cfg.setdefault('enabled', True)
                cfg.setdefault('display', shortcut.upper())

        # 规范化外观数值
        ap = default_settings['appearance']
        try:
            ap['window_opacity'] = min(1.0, max(0.3, float(ap['window_opacity'])))
        except Exception:
            ap['window_opacity'] = 0.75
        try:
            ap['display_duration'] = int(ap['display_duration'])
        except Exception:
            ap['display_duration'] = 1500
        try:
            ap['fade_duration'] = int(ap['fade_duration'])
        except Exception:
            ap['fade_duration'] = 500
        try:
            ap['font_size'] = min(32, max(8, int(ap['font_size'])))
        except Exception:
            ap['font_size'] = 12
        if not isinstance(ap.get('custom_position'), (list, tuple)):
            ap['custom_position'] = None
        try:
            ap['width_override'] = int(ap.get('width_override') or 0)
        except Exception:
            ap['width_override'] = 0
        try:
            ap['height_override'] = int(ap.get('height_override') or 0)
        except Exception:
            ap['height_override'] = 0

        return default_settings

    def save_settings(self):
        """保存设置"""
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            data = {
                k: v for k, v in self.settings.items()
                if k != 'auto_mode'
            }
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            safe_log(f"保存设置失败: {e}")
            return False


class KeyCaptureDialog:
    """按键捕获对话框"""

    MODIFIER_ORDER = ['ctrl', 'shift', 'alt', 'win']
    MAX_KEYS = 6

    def __init__(self, parent, on_capture=None, on_cancel=None):
        self.parent = parent
        self.on_capture = on_capture
        self.on_cancel = on_cancel
        self.dialog = None
        self.captured_keys = []
        self.is_capturing = False
        self.key_display = None
        self.last_event_time = 0

    def show(self):
        self.dialog = ctk.CTkToplevel(self.parent)
        self.dialog.title("按下快捷键")
        self.dialog.geometry("480x270")
        self.dialog.resizable(False, False)
        self.dialog.attributes('-topmost', True)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        ctk.CTkLabel(
            self.dialog,
            text="请按下要监听的组合键（最多 6 个键）",
            font=ctk.CTkFont(size=14, weight='bold'),
        ).pack(pady=(24, 4))
        ctk.CTkLabel(
            self.dialog,
            text="按 ESC 取消 · 按 Enter 确认",
            text_color='gray',
        ).pack()

        self.key_display = ctk.CTkLabel(
            self.dialog,
            text="等待按键...",
            font=ctk.CTkFont(size=18, weight='bold'),
            width=260,
            height=52,
            fg_color='#1E1E28',
            corner_radius=10,
        )
        self.key_display.pack(pady=18)

        btn_frame = ctk.CTkFrame(self.dialog, fg_color='transparent')
        btn_frame.pack(pady=(0, 18))
        ctk.CTkButton(btn_frame, text="确认", width=120,
                      command=self.confirm).pack(side='left', padx=8)
        ctk.CTkButton(btn_frame, text="取消", width=120,
                      fg_color='#3A3A3C', hover_color='#4A4A4C',
                      command=self.cancel).pack(side='left', padx=8)

        self.dialog.protocol("WM_DELETE_WINDOW", self.cancel)
        self.start_capture()

    def start_capture(self):
        self.is_capturing = True
        self.captured_keys = []
        # 只挂自己的钩子，不清理主监听：避免与监听线程的 unhook_all 竞争
        # 导致录制窗口失效（ESC 等按键收不到）。
        try:
            keyboard.hook(self.on_key_event)
        except Exception as e:
            safe_log(f"录制钩子挂载失败: {e}")

    def on_key_event(self, event):
        """处理按键事件（在键盘监听线程中运行）"""
        if not self.is_capturing:
            return
        if event.event_type != keyboard.KEY_DOWN:
            return
        # 过滤按住键时的系统自动重复
        if event.time - self.last_event_time < 0.03:
            return

        key_name = event.name.lower()
        key_name = KEY_NAME_MAP.get(key_name, key_name)

        if key_name == 'esc':
            self.safe_call(self.cancel)
            return

        if key_name == 'enter':
            if len(self.captured_keys) > 0:
                self.safe_call(self.confirm)
            else:
                self.add_key('enter')
            return

        self.add_key(key_name)

    def add_key(self, key_name):
        if key_name in self.captured_keys:
            return
        if len(self.captured_keys) >= self.MAX_KEYS:
            return
        self.last_event_time = time.time()
        if key_name in self.MODIFIER_ORDER:
            self.captured_keys.append(key_name)
            self.captured_keys.sort(key=lambda k: (
                self.MODIFIER_ORDER.index(k) if k in self.MODIFIER_ORDER else 99))
        else:
            self.captured_keys.append(key_name)
        self.update_display()

    def safe_call(self, func):
        try:
            if self.dialog:
                self.dialog.after(0, func)
        except Exception:
            try:
                func()
            except Exception:
                pass

    def update_display(self):
        if self.dialog and self.key_display:
            text = self.get_shortcut_string() or '等待按键...'
            try:
                self.dialog.after(0, lambda: self.key_display.configure(text=text))
            except Exception:
                pass

    def get_shortcut_string(self):
        return '+'.join(self.captured_keys)

    def confirm(self):
        if len(self.captured_keys) == 0:
            return
        shortcut = self.get_shortcut_string()
        callback = self.on_capture
        self.cleanup()
        if self.dialog:
            try:
                self.dialog.destroy()
            except Exception:
                pass
            self.dialog = None
        if callback:
            callback(shortcut)

    def cancel(self):
        callback = self.on_cancel
        self.cleanup()
        if self.dialog:
            try:
                self.dialog.destroy()
            except Exception:
                pass
            self.dialog = None
        if callback:
            callback()

    def cleanup(self):
        self.is_capturing = False
        try:
            keyboard.unhook(self.on_key_event)
        except Exception:
            pass


class ShortcutNotifier:
    def __init__(self):
        self.settings_manager = Settings()
        self.settings = self.settings_manager.settings

        self.window = None
        self.canvas = None
        self.root = ctk.CTk()
        self.root.withdraw()
        self.root.attributes('-alpha', 0.0)

        # DPI 字号补偿：CustomTkinter 使进程 DPI 感知后，Tk 仍按 96 DPI 渲染字体，
        # 需要按屏幕缩放放大字号，才能让“12 号”在所有分辨率下都显示为真正的 12 磅。
        self.font_scale = self.get_dpi_scale()
        self._migrate_font_size()

        self.current_shortcut = None
        self.current_count = 0
        self.current_message = ""
        self.current_after_id = None

        self.last_activity_time = time.time()
        self.last_hotkey_reload_time = 0
        self.last_listener_restart_time = 0

        ap = self.settings['appearance']
        self.display_duration = ap['display_duration']
        self.fade_duration = ap['fade_duration']
        self.fade_steps = 20
        self.fade_alpha = ap['window_opacity']
        self.fade_step = 0
        self.is_fading = False
        self.fade_after_id = None

        self.window_created_time = 0
        self.watchdog_after_id = None
        self.watchdog_active = False
        self.heartbeat_after_id = None

        self.min_width = 100
        self.max_width = 380
        self.horizontal_padding = 40
        self.window_width = 200
        self.window_height = 45
        self.measure_font = tkfont.Font(
            root=self.root, family='Microsoft YaHei', weight='bold')

        self.running = True
        self.tray_icon = None
        self.settings_window = None
        self.shortcut_rows = {}
        self.my_shortcuts_frame = None
        self.my_empty_label = None
        self.presets_frame = None
        self.presets_search_var = None
        self.presets_search_after = None
        self.expanded_presets = set()
        self.preset_cards = {}
        self.preset_count_labels = {}
        self.preset_row_vars = {}
        self.preset_display_vars = {}
        self.preset_bodies = {}
        self.preset_expand_buttons = {}
        self.capture_dialog = None
        self.settings_snapshot = None

        # 键盘监听线程控制
        self.listener_thread = None
        self.listener_reload = threading.Event()
        self.listener_stop = threading.Event()
        self.suspend_hotkeys = False
        self.capture_active = False
        self.matched_preset_ids = set()
        self.preset_switch_vars = {}
        self.active_shortcuts = self.compute_active_shortcuts()
        self.active_canonical = {
            self._canonicalize(k): (k, display)
            for k, display in self.active_shortcuts.items()
        }
        self.poll_keys = set()
        self.poll_prev_down = set()
        self.poll_prev_mods = set()
        self._build_poll_keys()
        self.pressed_keys = set()
        self.event_queue = queue.Queue()

        # 持续输出模式
        self.continuous_mode = bool(self.settings.get('continuous_mode', False))
        self.cont_pressed = set()
        self.cont_keys = []
        self.cont_count = 1
        self.cont_active = False

        # 拖拽定位
        self._drag_offset = None
        self._drag_moved = False
        self._drag_hint = False

    # ---------- 快捷键集合计算 ----------

    def compute_active_shortcuts(self):
        """计算当前生效的快捷键集合（用户自定义优先）"""
        active = {}
        for sc, cfg in self.settings.get('shortcuts', {}).items():
            if cfg.get('enabled', True):
                active[sc] = cfg.get('display') or sc

        auto_ids = set(self.matched_preset_ids) if self.settings.get('auto_mode') else set()
        manual_ids = {
            pid for pid, st in self.settings.get('preset_states', {}).items()
            if st.get('enabled')
        }

        ordered = [pid for pid in PRESET_ORDER if pid in auto_ids]
        for pid in PRESET_ORDER:
            if pid != 'windows' and pid in manual_ids and pid not in ordered:
                ordered.append(pid)
        if 'windows' in manual_ids and 'windows' not in ordered:
            ordered.append('windows')

        for pid in ordered:
            preset = PRESET_LIBRARY.get(pid)
            if not preset:
                continue
            state = self.settings.get('preset_states', {}).get(pid, {})
            overrides = state.get('shortcuts', {})
            for sc, cfg in preset['shortcuts'].items():
                if sc in active:
                    continue
                ov = overrides.get(sc, {})
                if ov.get('enabled') is False:
                    continue
                display = ov.get('display') or cfg.get('display') or sc
                active[sc] = display
        return active

    def sync_hotkeys(self):
        """活动快捷键变化时通知监听线程重新注册"""
        active = self.compute_active_shortcuts()
        if active != self.active_shortcuts:
            self.active_shortcuts = active
            self.active_canonical = {
                self._canonicalize(k): (k, display)
                for k, display in active.items()
            }
            self._build_poll_keys()
            self.reload_hotkeys()

    # ---------- DPI 与版本迁移 ----------

    def get_dpi_scale(self):
        """屏幕缩放系数：字号补偿用（200% 缩放 = 2.0）"""
        try:
            dpi = ctypes.windll.user32.GetDpiForSystem()
            if dpi and dpi != 96:
                return dpi / 96.0
        except Exception:
            pass
        return 1.0

    def _migrate_font_size(self):
        """把旧版本（未做 DPI 补偿）里为了补偿而调大的字号换算回真实磅值"""
        try:
            if int(self.settings.get('settings_version') or 0) >= 3:
                return
            ap = self.settings['appearance']
            size = int(ap.get('font_size') or 0)
            if size > 16 and self.font_scale > 1.0:
                new_size = min(32, max(8, round(size / self.font_scale)))
                ap['font_size'] = new_size
                self.settings['settings_version'] = 3
                self.settings_manager.save_settings()
                safe_log(f"字号迁移 {size} -> {new_size} (DPI x{self.font_scale})")
            else:
                self.settings['settings_version'] = 3
        except Exception as e:
            safe_log(f"字号迁移失败: {e}")

    def on_foreground_matched(self, matched):
        try:
            self.root.after(0, lambda: self._apply_foreground_match(matched))
        except Exception:
            pass

    def _apply_foreground_match(self, matched):
        if not self.settings.get('auto_mode'):
            return
        if matched != self.matched_preset_ids:
            self.matched_preset_ids = matched
            self.sync_hotkeys()

    def refresh_foreground_match(self):
        """立即按当前前台窗口刷新一次匹配"""
        if self.settings.get('auto_mode'):
            exe, title = get_foreground_window_info()
            self.matched_preset_ids = {
                pid for pid, preset in PRESET_LIBRARY.items()
                if preset_matches(preset, exe, title)
            }
        else:
            self.matched_preset_ids = set()
        self.sync_hotkeys()

    # ---------- 定时器与窗口生命周期 ----------

    def get_window_lifetime(self):
        if self._drag_hint:
            return 22
        return (self.display_duration + self.fade_duration) / 1000 + 2

    def clear_all_timers(self):
        timers = [self.current_after_id, self.fade_after_id,
                  self.watchdog_after_id, self.heartbeat_after_id]
        for timer in timers:
            if timer:
                try:
                    self.root.after_cancel(timer)
                except Exception:
                    pass
        self.current_after_id = None
        self.fade_after_id = None
        self.watchdog_after_id = None
        self.heartbeat_after_id = None
        self.watchdog_active = False

    def start_watchdog(self):
        if self.watchdog_active:
            return
        self.watchdog_active = True
        self.window_created_time = time.time()
        self.watchdog_check()

    def watchdog_check(self):
        if not self.watchdog_active or not self.window:
            self.watchdog_active = False
            return
        try:
            if not self.window.winfo_exists():
                self.watchdog_active = False
                return
            if time.time() - self.window_created_time > self.get_window_lifetime():
                self.force_close_window()
                return
            # 保持置顶：防止 Win+D 等操作后提示窗被新出现的窗口盖住
            try:
                if self.window and self.window.winfo_exists():
                    self.window.lift()
            except Exception:
                pass
            self.watchdog_after_id = self.root.after(500, self.watchdog_check)
        except Exception:
            self.watchdog_active = False

    def start_heartbeat(self):
        self.heartbeat_check()

    def heartbeat_check(self):
        try:
            if not (self.listener_thread and self.listener_thread.is_alive()):
                self.start_listener()
            # 长时间无按键后（含睡眠唤醒场景）重新注册一次热键，避免钩子失效
            now = time.time()
            if (now - self.last_activity_time > 120
                    and now - self.last_hotkey_reload_time > 60):
                self.last_hotkey_reload_time = now
                self.reload_hotkeys()
            # 钩子健康检查：系统有输入但我们长时间没收到 → 低级钩子可能被
            # 系统超时卸载（任务管理器等场景），需要重启监听线程
            if (now - self.last_activity_time > 25
                    and now - self.last_listener_restart_time > 60
                    and not is_foreground_elevated()):
                last_input = get_last_input_wall_time()
                if last_input is not None and last_input > now - 25:
                    self.last_listener_restart_time = now
                    safe_log("检测到键盘钩子可能失效，重启监听线程")
                    self.force_restart_listener()
            if self.window and time.time() - self.window_created_time > self.get_window_lifetime():
                self.force_close_window()
        except Exception as e:
            safe_log(f"心跳检测异常: {e}")
        finally:
            self.heartbeat_after_id = self.root.after(15000, self.heartbeat_check)

    def force_restart_listener(self):
        """低级钩子被系统卸载后，强制重启键盘库的监听线程"""
        try:
            keyboard.unhook_all()
            try:
                # 让 keyboard 库在下次 add_hotkey 时重新创建监听线程与钩子
                keyboard._listener.listening = False
            except Exception:
                pass
            self.reload_hotkeys()
        except Exception as e:
            safe_log(f"重启监听失败: {e}")

    def force_close_window(self):
        self.clear_all_timers()
        self.is_fading = False
        self.watchdog_active = False
        self._drag_hint = False
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None
            self.canvas = None
        self.current_shortcut = None
        self.current_count = 0
        self.current_message = ""

    # ---------- 键盘监听 ----------

    def start_listener(self):
        if self.listener_thread and self.listener_thread.is_alive():
            return
        self.listener_thread = threading.Thread(
            target=self.keyboard_listener, daemon=True)
        self.listener_thread.start()

    def keyboard_listener(self):
        """监听线程：只负责安装一个原始键事件钩子。
        钩子回调只做状态更新与入队（微秒级），不再直接触碰 Tk，
        从根本上避免回调超时被系统卸载。"""
        while not self.listener_stop.is_set():
            if not self.suspend_hotkeys:
                try:
                    keyboard.unhook_all()
                    keyboard.hook(self._raw_key_event)
                except Exception as e:
                    safe_log(f"监听注册异常: {e}")
            self.listener_reload.wait()
            self.listener_reload.clear()
        try:
            keyboard.unhook_all()
        except Exception:
            pass

    def _normalize_key(self, name):
        name = (name or '').lower()
        return RAW_KEY_MAP.get(name, name)

    def _canonicalize(self, shortcut):
        """把快捷键规范化为统一修饰键顺序（ctrl+alt+shift+win+主键）"""
        parts = shortcut.split('+')
        mods = sorted([p for p in parts if p in MOD_ORDER],
                      key=lambda p: MOD_ORDER[p])
        rest = [p for p in parts if p not in MOD_ORDER]
        return '+'.join(mods + rest)

    def _raw_key_event(self, event):
        """键盘原始事件回调（在键盘库线程运行，必须极轻量：
        只更新按压状态并把事件放入队列，不做任何匹配/Tk 操作）"""
        self.last_activity_time = time.time()
        try:
            name = self._normalize_key(event.name)
            if event.event_type != keyboard.KEY_DOWN:
                self.pressed_keys.discard(name)
                self.event_queue.put_nowait(('up', name))
                return
            if name in self.pressed_keys:
                # 按住自动重复：不重复触发
                self.event_queue.put_nowait(('repeat', name))
                return
            self.pressed_keys.add(name)
            self.event_queue.put_nowait(('down', name))
        except Exception:
            pass

    def _key_down(self, vk):
        """查询某个虚拟键当前是否被按下（GetAsyncKeyState，跨权限窗口有效）"""
        try:
            state = ctypes.windll.user32.GetAsyncKeyState(vk)
            return bool(state & 0x8000)
        except Exception:
            return False

    def _mods_down(self):
        """读取当前真实按下的修饰键（不依赖可能卡死的本地状态）"""
        mods = []
        for m in MOD_ORDER:
            if m == 'win':
                if self._key_down(0x5B) or self._key_down(0x5C):
                    mods.append(m)
            elif self._key_down(MOD_VK[m]):
                mods.append(m)
        return mods

    def _build_poll_keys(self):
        """从活动快捷键中提取需要轮询的键位（钩子失效/权限过滤时兜底）"""
        keys = set()
        for combo in self.active_canonical:
            for part in combo.split('+'):
                if part not in MOD_ORDER:
                    keys.add(part)
        self.poll_keys = keys
        self.poll_prev_down = set()
        self.poll_prev_mods = set()

    def _poll_key_states(self):
        """GetAsyncKeyState 轮询兜底：钩子失效或前台为管理员窗口时启用"""
        if not self.poll_keys:
            return
        user32 = ctypes.windll.user32
        now_down = set()
        for key in self.poll_keys:
            vk = VK_MAP.get(key)
            if vk and (user32.GetAsyncKeyState(vk) & 0x8000):
                now_down.add(key)
        for key in now_down - self.poll_prev_down:
            self._process_key_event(('down', key))
        self.poll_prev_down = now_down

        if self.continuous_mode:
            now_mods = set(self._mods_down())
            for mod in now_mods - self.poll_prev_mods:
                self._process_key_event(('down', mod))
            for mod in self.poll_prev_mods - now_mods:
                self._process_key_event(('up', mod))
            self.poll_prev_mods = now_mods

    def _reconcile_key_state(self):
        """用真实按键状态校准本地按压记录，修复任务管理器等场景下
        因 KEY_UP 丢失导致的“修饰键卡死”问题"""
        try:
            # 本地认为按下、实际已松开 → 清除
            for name in list(self.pressed_keys):
                vk = MOD_VK.get(name) or VK_MAP.get(name)
                if vk and not self._key_down(vk):
                    self.pressed_keys.discard(name)
            # 实际按下、本地缺失 → 补录（权限过滤期间按下的键）
            for name, vk in MOD_VK.items():
                if name == 'win':
                    if self._key_down(0x5B) or self._key_down(0x5C):
                        self.pressed_keys.add(name)
                elif self._key_down(vk):
                    self.pressed_keys.add(name)

            # 持续输出模式同样需要校准：过滤期间丢失的 KEY_UP 会让
            # cont_pressed 残留旧键、cont_active 一直为 True，导致
            # 即使任务管理器关闭后持续输出仍显示错误内容。
            if self.continuous_mode:
                changed = False
                for name in list(self.cont_pressed):
                    vk = MOD_VK.get(name) or VK_MAP.get(name)
                    if vk and not self._key_down(vk):
                        self.cont_pressed.discard(name)
                        changed = True
                for name, vk in MOD_VK.items():
                    down = (self._key_down(0x5B) or self._key_down(0x5C)) \
                        if name == 'win' else self._key_down(vk)
                    if down and name not in self.cont_pressed:
                        self.cont_pressed.add(name)
                        changed = True
                any_key_down = any(
                    self._key_down(vk)
                    for k in self.cont_keys
                    if (vk := VK_MAP.get(k)))
                if not self.cont_pressed and not any_key_down:
                    if self.cont_active or self.cont_keys:
                        self.cont_active = False
                        self.cont_keys = []
                        self.cont_count = 1
                        changed = True
                if changed and self.cont_active:
                    self._show_continuous()
        except Exception:
            pass

    def _poll_key_events(self):
        """主线程轮询：从队列取事件并驱动显示（每 25ms 一次）"""
        try:
            while True:
                item = self.event_queue.get_nowait()
                self._process_key_event(item)
        except queue.Empty:
            pass
        except Exception as e:
            safe_log(f"事件处理异常: {e}")
        finally:
            try:
                # 校准按键状态 + 钩子失效/权限过滤时轮询兜底
                self._reconcile_key_state()
                now = time.time()
                elevated = is_foreground_elevated()
                hook_silent = now - self.last_activity_time > 3
                if elevated or hook_silent:
                    self._poll_key_states()
            except Exception:
                pass
            try:
                self.root.after(25, self._poll_key_events)
            except Exception:
                pass

    def _process_key_event(self, item):
        if self.suspend_hotkeys or not self.running:
            return
        kind = item[0]
        if self.continuous_mode:
            if kind == 'down':
                name = item[1]
                self._process_continuous_event(
                    ('mod', name) if name in MOD_ORDER else ('key', name))
            elif kind == 'up':
                self._process_continuous_event(('up', item[1]))
            return
        if kind == 'down' and item[1] not in MOD_ORDER:
            # 用真实修饰键状态匹配，避免本地状态卡死导致失配
            name = item[1]
            mods = self._mods_down()
            combo = self._canonicalize('+'.join(mods + [name]))
            target = self.active_canonical.get(combo)
            if target:
                target_key, display = target
                self._handle_shortcut(target_key, display)

    # ---------- 持续输出模式 ----------

    def _process_continuous_event(self, item):
        kind = item[0]
        if kind == 'repeat':
            return
        name = item[1]
        if kind == 'up':
            self.cont_pressed.discard(name)
            if not self.cont_pressed:
                self.cont_active = False
            return
        if kind == 'mod':
            if not self.cont_active:
                self.cont_active = True
                self.cont_keys = []
                self.cont_count = 1
            self.cont_pressed.add(name)
            self._show_continuous()
        elif kind == 'key':
            if not self.cont_active:
                return
            self.cont_pressed.add(name)
            if not self.cont_keys:
                self.cont_keys.append(name)
                self.cont_count = 1
            elif name == self.cont_keys[-1]:
                self.cont_count += 1
            else:
                self.cont_keys.append(name)
                self.cont_count = 1
            self._show_continuous()

    def _show_continuous(self):
        mods = sorted([m for m in self.cont_pressed if m in MOD_ORDER],
                      key=lambda m: MOD_ORDER[m])
        parts = mods + self.cont_keys
        text = self.format_display_name('+'.join(parts))
        if self.cont_count > 1:
            text += f" ×{self.cont_count}"
        # 内容没变化就不重复刷新（校准轮询每 25ms 会调用）
        if text == self.current_message:
            return
        self.current_count = 1
        self._show_message(text, '__continuous__')

    def reload_hotkeys(self):
        self.listener_reload.set()

    def update_suspend(self):
        """根据设置窗口/录制窗口是否打开，决定是否挂起快捷键响应"""
        settings_open = bool(
            self.settings_window and self.settings_window.winfo_exists())
        suspended = self.capture_active or settings_open
        if suspended != self.suspend_hotkeys:
            self.suspend_hotkeys = suspended
            self.reload_hotkeys()

    def _handle_shortcut(self, shortcut_key, message):
        try:
            self.last_activity_time = time.time()
            if shortcut_key == self.current_shortcut:
                self.current_count += 1
            else:
                self.current_count = 1
            self._show_message(message, shortcut_key)
        except Exception as e:
            safe_log(f"处理快捷键 {shortcut_key} 失败: {e}")

    # ---------- 悬浮提示窗 ----------

    def compute_auto_size(self, text_width, text_height):
        """根据文本实际渲染尺寸计算窗口大小（支持固定尺寸覆盖）"""
        ap = self.settings['appearance']
        width_override = int(ap.get('width_override') or 0)
        height_override = int(ap.get('height_override') or 0)
        if width_override > 0:
            width = max(80, min(width_override, 2000))
        else:
            width = min(max(text_width + self.horizontal_padding,
                            self.min_width), self.max_width)
        if height_override > 0:
            height = max(30, min(height_override, 600))
        else:
            height = max(40, text_height + 22)
        return width, height

    def _estimate_text_size(self, text, font_size):
        """粗略估算文本尺寸（仅用于创建窗口前的初值，最终以渲染测量为准）"""
        try:
            self.measure_font.configure(
                size=max(6, int(font_size * self.font_scale)))
            width = int(self.measure_font.measure(text))
            height = int(self.measure_font.metrics('linespace'))
        except Exception:
            width = len(text) * font_size
            height = font_size + 10
        if width <= 0:
            width = len(text) * font_size
        if height <= 0:
            height = font_size + 10
        return width, height

    def _draw_content(self, text, font_size):
        """在画布上绘制内容（按当前窗口尺寸居中，超宽自动换行）"""
        self.canvas.delete('all')
        self.draw_rounded_rect()
        wrap_width = max(20, self.window_width - self.horizontal_padding)
        render_size = max(6, int(font_size * self.font_scale))
        self.canvas.create_text(
            self.window_width // 2,
            self.window_height // 2,
            text=text,
            width=wrap_width,
            justify='center',
            font=('Microsoft YaHei', render_size, 'bold'),
            fill=self.settings['appearance']['text_color'])

    def _get_measure_wrap_width(self):
        """测量文本时使用的最大换行宽度（固定宽度或自动上限）"""
        ap = self.settings['appearance']
        width_override = int(ap.get('width_override') or 0)
        limit = width_override if width_override > 0 else self.max_width
        return max(20, limit - self.horizontal_padding)

    def _draw_and_measure(self, text, font_size):
        """绘制内容并返回文本实际渲染尺寸（只测文字，不含背景）"""
        self.canvas.delete('all')
        self.draw_rounded_rect()
        wrap_width = self._get_measure_wrap_width()
        render_size = max(6, int(font_size * self.font_scale))
        item = self.canvas.create_text(
            self.window_width // 2,
            self.window_height // 2,
            text=text,
            width=wrap_width,
            justify='center',
            font=('Microsoft YaHei', render_size, 'bold'),
            fill=self.settings['appearance']['text_color'])
        try:
            bbox = self.canvas.bbox(item)
            if bbox:
                return max(bbox[2] - bbox[0], 0), max(bbox[3] - bbox[1], 0)
        except Exception:
            pass
        return self._estimate_text_size(text, font_size)

    def get_window_position(self, width, height):
        ap = self.settings['appearance']
        position = ap['position']

        # Tk 的窗口几何坐标与 WinAPI 一致（物理像素）；winfo_screenwidth
        # 返回的是缩放后的逻辑值，不能用于定位，因此这里统一用 WinAPI 物理坐标。
        virtual = get_virtual_screen_bounds()
        if virtual:
            vleft, vtop, vright, vbottom = virtual
        else:
            vleft, vtop = 0, 0
            vright = self.root.winfo_screenwidth()
            vbottom = self.root.winfo_screenheight()
        # 兜底：桌面边界异常（如启动瞬间读到 0）时退回主屏物理尺寸
        if vright - vleft <= 0 or vbottom - vtop <= 0:
            try:
                user32 = ctypes.windll.user32
                vright = vleft + user32.GetSystemMetrics(0)
                vbottom = vtop + user32.GetSystemMetrics(1)
            except Exception:
                vright = self.root.winfo_screenwidth()
                vbottom = self.root.winfo_screenheight()

        if position == 'custom' and ap.get('custom_position'):
            x, y = ap['custom_position'][:2]
            x = min(max(int(x), vleft), max(vright - width, vleft))
            y = min(max(int(y), vtop), max(vbottom - height, vtop))
            return int(x), int(y)

        # 优先在鼠标所在显示器的工作区内定位，避免出现在不用的屏幕上
        area = get_work_area_at_cursor()
        if area and area[2] - area[0] > 0 and area[3] - area[1] > 0:
            left, top, right, bottom = area
        else:
            left, top, right, bottom = vleft, vtop, vright, vbottom
        area_width = max(right - left - width, 0)
        area_height = max(bottom - top - height, 0)
        positions = {
            'bottom-center': (left + area_width // 2, bottom - height - 16),
            'bottom-right': (right - width - 20, bottom - height - 16),
            'bottom-left': (left + 20, bottom - height - 16),
            'top-center': (left + area_width // 2, top + 16),
            'top-right': (right - width - 20, top + 16),
            'top-left': (left + 20, top + 16),
            'center': (left + area_width // 2, top + area_height // 2),
        }
        x, y = positions.get(position, positions['bottom-center'])
        # 预设位置同样钳位到可见桌面范围内，防止越界
        x = min(max(x, vleft), max(vright - width, vleft))
        y = min(max(y, vtop), max(vbottom - height, vtop))
        return int(x), int(y)

    def _show_message(self, message, shortcut_id):
        self.cancel_fade()
        if self.current_after_id:
            try:
                self.root.after_cancel(self.current_after_id)
            except Exception:
                pass
            self.current_after_id = None
        self.current_shortcut = shortcut_id
        self.current_message = message
        if self.window:
            self.update_window_content()
            self.window_created_time = time.time()
            try:
                self.window.lift()
                self.window.attributes('-alpha', self.fade_alpha)
            except Exception:
                pass
        else:
            self.create_floating_window()
        self.reset_timer()

    def cancel_fade(self):
        self.is_fading = False
        if self.fade_after_id:
            try:
                self.root.after_cancel(self.fade_after_id)
            except Exception:
                pass
            self.fade_after_id = None

    def update_window_content(self):
        if not (self.window and self.canvas):
            return
        if self.current_count > 1:
            display_text = f"{self.current_message} ×{self.current_count}"
        else:
            display_text = self.current_message
        font_size = self.settings['appearance']['font_size']
        text_w, text_h = self._draw_and_measure(display_text, font_size)
        new_width, new_height = self.compute_auto_size(text_w, text_h)
        if (new_width, new_height) != (self.window_width, self.window_height):
            self.window_width, self.window_height = new_width, new_height
            x, y = self.get_window_position(new_width, new_height)
            try:
                self.window.geometry(f'{new_width}x{new_height}+{x}+{y}')
                self.canvas.config(width=new_width, height=new_height)
                self._draw_content(display_text, font_size)
            except Exception as e:
                safe_log(f"更新窗口尺寸失败: {e}")
        try:
            self.window.attributes('-alpha', self.fade_alpha)
        except Exception:
            pass

    def draw_rounded_rect(self):
        if not self.canvas:
            return
        radius = 8
        border_color = self.settings['appearance']['border_color']
        bg_color = self.settings['appearance']['bg_color']
        if border_color:
            self.canvas.create_polygon(
                rounded_rect_points(self.window_width, self.window_height, radius, 1),
                smooth=True, fill=border_color)
        self.canvas.create_polygon(
            rounded_rect_points(self.window_width, self.window_height, radius, 0),
            smooth=True, fill=bg_color)

    def create_floating_window(self):
        if self.window:
            return
        try:
            self.window = tk.Toplevel(self.root)
            self.window.withdraw()
            self.window.overrideredirect(True)
            self.window.attributes('-topmost', True)
            self.window.attributes('-toolwindow', True)

            font_size = self.settings['appearance']['font_size']
            est_w, est_h = self._estimate_text_size(
                self.current_message, font_size)
            width, height = self.compute_auto_size(est_w, est_h)
            x, y = self.get_window_position(width, height)
            self.window_width, self.window_height = width, height
            self.window.geometry(f'{width}x{height}+{x}+{y}')

            self.canvas = tk.Canvas(
                self.window,
                width=width,
                height=height,
                highlightthickness=0,
                bg=self.settings['appearance']['bg_color'],
                cursor='fleur')
            self.canvas.pack(fill='both', expand=True)

            # 先按真实渲染尺寸校正一次窗口大小（隐藏状态下进行，避免闪烁）
            text_w, text_h = self._draw_and_measure(
                self.current_message, font_size)
            new_width, new_height = self.compute_auto_size(text_w, text_h)
            if (new_width, new_height) != (width, height):
                self.window_width, self.window_height = new_width, new_height
                x, y = self.get_window_position(new_width, new_height)
                self.window.geometry(f'{new_width}x{new_height}+{x}+{y}')
                self.canvas.config(width=new_width, height=new_height)
                self._draw_content(self.current_message, font_size)

            # 拖拽定位
            self.window.bind('<ButtonPress-1>', self.on_drag_start)
            self.window.bind('<B1-Motion>', self.on_drag_move)
            self.window.bind('<ButtonRelease-1>', self.on_drag_end)
            self.canvas.bind('<ButtonPress-1>', self.on_drag_start)
            self.canvas.bind('<B1-Motion>', self.on_drag_move)
            self.canvas.bind('<ButtonRelease-1>', self.on_drag_end)

            self.window.update_idletasks()
            self.window.deiconify()
            try:
                self.window.lift()
            except Exception:
                pass
            self.window.attributes('-alpha', self.fade_alpha)
            self.start_watchdog()
            self.reset_timer()
            # 样式在窗口完全映射后再应用，并在稍后补一次，避免被 Tk 重置
            self._apply_notification_styles()
            try:
                self.window.after(50, self._apply_notification_styles)
                self.window.after(300, self._apply_notification_styles)
            except Exception:
                pass
        except Exception as e:
            safe_log(f"创建悬浮窗失败: {e}")
            self.force_close_window()

    def _apply_notification_styles(self):
        """给提示窗加扩展样式：不出现在 Alt+Tab / 任务栏，且不抢焦点"""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.window.winfo_id())
            if not hwnd:
                return
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000
            user32 = ctypes.windll.user32
            user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            user32.GetWindowLongW.restype = ctypes.c_long
            user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
            user32.SetWindowLongW.restype = ctypes.c_long
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
        except Exception as e:
            safe_log(f"设置提示窗样式失败: {e}")

    # ---------- 拖拽定位 ----------

    def on_drag_start(self, event):
        if not self.window:
            return
        # 全部使用 WinAPI 物理坐标：窗口位置(winfo_x)、光标(GetCursorPos)、
        # 桌面边界(GetSystemMetrics) 三者单位一致，避免 DPI 缩放导致错位。
        cursor = get_cursor_pos()
        if cursor is None:
            cursor = (event.x_root, event.y_root)
        self._drag_offset = (
            cursor[0] - self.window.winfo_x(),
            cursor[1] - self.window.winfo_y())
        self._drag_moved = False
        # 拖动期间暂停自动消失
        if self.current_after_id:
            try:
                self.root.after_cancel(self.current_after_id)
            except Exception:
                pass
            self.current_after_id = None
        self.cancel_fade()
        self.window_created_time = time.time()
        # 捕获指针：快速拖动时鼠标离开窗口也能继续收到移动事件
        try:
            self.window.grab_set()
        except Exception:
            pass

    def on_drag_move(self, event):
        if not self.window or self._drag_offset is None:
            return
        cursor = get_cursor_pos()
        if cursor is None:
            cursor = (event.x_root, event.y_root)
        px, py = cursor
        x = px - self._drag_offset[0]
        y = py - self._drag_offset[1]
        virtual = get_virtual_screen_bounds()
        if virtual:
            vleft, vtop, vright, vbottom = virtual
        else:
            vleft, vtop = 0, 0
            vright = self.root.winfo_screenwidth()
            vbottom = self.root.winfo_screenheight()
        x = min(max(x, vleft), max(vright - self.window_width, vleft))
        y = min(max(y, vtop), max(vbottom - self.window_height, vtop))
        try:
            self.window.geometry(f'+{int(x)}+{int(y)}')
            self._drag_moved = True
        except Exception:
            pass

    def on_drag_end(self, event):
        if not self.window or self._drag_offset is None:
            return
        self._drag_offset = None
        try:
            self.window.grab_release()
        except Exception:
            pass
        if not self._drag_moved:
            # 只是点了一下，不改变位置设置
            self.reset_timer()
            return
        try:
            try:
                self.window.update_idletasks()
            except Exception:
                pass
            x = self.window.winfo_x()
            y = self.window.winfo_y()
            self.settings['appearance']['custom_position'] = [x, y]
            self.settings['appearance']['position'] = 'custom'
            self.settings_manager.save_settings()
            if hasattr(self, 'position_var'):
                try:
                    self.position_var.set('custom')
                except Exception:
                    pass
            if hasattr(self, 'update_preview'):
                try:
                    self.update_preview()
                except Exception:
                    pass
        except Exception as e:
            safe_log(f"保存拖拽位置失败: {e}")

        self.reset_timer()

        if self._drag_hint:
            self._drag_hint = False
            try:
                messagebox.showinfo("位置已保存", "提示框位置已保存为自定义位置")
            except Exception:
                pass
            self.force_close_window()

    def show_drag_hint(self):
        if self.window:
            self.force_close_window()
        self._drag_hint = True
        self._show_message("按住这里拖动到目标位置，松开即保存", '__drag__')
        if self.current_after_id:
            try:
                self.root.after_cancel(self.current_after_id)
            except Exception:
                pass
        self.current_after_id = self.root.after(20000, self.start_fade_out)

    # ---------- 淡出动画 ----------

    def start_fade_out(self):
        if not self.window:
            return
        self.is_fading = True
        self.fade_step = 0
        self.perform_fade()

    def perform_fade(self):
        if not self.window or not self.is_fading:
            return
        self.fade_step += 1
        if self.fade_step >= self.fade_steps:
            self.is_fading = False
            self.force_close_window()
            return
        progress = self.fade_step / self.fade_steps
        current_alpha = self.fade_alpha * (1 - progress)
        try:
            self.window.attributes('-alpha', max(0, current_alpha))
            interval = max(10, self.fade_duration // self.fade_steps)
            self.fade_after_id = self.root.after(interval, self.perform_fade)
        except Exception:
            self.is_fading = False
            self.force_close_window()

    def reset_timer(self):
        if self.current_after_id:
            try:
                self.root.after_cancel(self.current_after_id)
            except Exception:
                pass
        self.current_after_id = self.root.after(
            self.display_duration, self.start_fade_out)

    # ---------- 设置窗口 ----------

    def open_settings(self):
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_force()
            return

        self.settings_snapshot = copy.deepcopy(self.settings)
        self.capture_active = False

        win = ctk.CTkToplevel(self.root)
        self.settings_window = win
        win.title(f"{APP_NAME}设置")
        win.geometry("980x720")
        win.minsize(880, 640)
        win.attributes('-topmost', False)
        win.protocol("WM_DELETE_WINDOW", self.cancel_settings)

        header = ctk.CTkFrame(win, fg_color='transparent')
        header.pack(fill='x', padx=24, pady=(18, 6))
        ctk.CTkLabel(
            header, text=APP_NAME,
            font=ctk.CTkFont(size=22, weight='bold')).pack(side='left')
        ctk.CTkLabel(
            header, text="  快捷键视觉反馈 · 设置",
            text_color='gray').pack(side='left', padx=8)

        tabview = ctk.CTkTabview(win, fg_color='transparent')
        tabview.pack(fill='both', expand=True, padx=18, pady=8)
        tab_my = tabview.add("我的快捷键")
        tab_presets = tabview.add("软件预设")
        tab_appearance = tabview.add("外观")
        tab_system = tabview.add("系统")

        self.build_my_shortcuts_tab(tab_my)
        self.build_presets_tab(tab_presets)
        self.build_appearance_tab(tab_appearance)
        self.build_system_tab(tab_system)

        footer = ctk.CTkFrame(win, fg_color='transparent')
        footer.pack(fill='x', padx=24, pady=(4, 18))
        ctk.CTkLabel(
            footer, text="修改后点击“保存”生效",
            text_color='gray').pack(side='left')
        ctk.CTkButton(
            footer, text="取消", width=96,
            fg_color='#3A3A3C', hover_color='#4A4A4C',
            command=self.cancel_settings).pack(side='right', padx=6)
        ctk.CTkButton(
            footer, text="保存", width=130,
            command=self.apply_settings).pack(side='right')

        # 保证设置窗口正常显示在最前面（首次创建时 Tk 可能将其置于底层）
        try:
            win.lift()
            win.focus_force()
            win.after(120, lambda: win.lift())
        except Exception:
            pass
        self.update_suspend()

    # ---------- 我的快捷键页 ----------

    def build_my_shortcuts_tab(self, parent):
        toolbar = ctk.CTkFrame(parent, fg_color='transparent')
        toolbar.pack(fill='x', padx=12, pady=(12, 4))
        ctk.CTkButton(
            toolbar, text="＋ 录制新快捷键", width=150,
            command=self.capture_new_shortcut).pack(side='left')
        ctk.CTkLabel(
            toolbar, text="自己录制的快捷键优先级最高，不受预设开关影响",
            text_color='gray').pack(side='left', padx=12)

        self.my_shortcuts_frame = ctk.CTkScrollableFrame(
            parent, fg_color='transparent')
        self.my_shortcuts_frame.pack(fill='both', expand=True, padx=12, pady=10)

        self.shortcut_rows = {}
        self.my_empty_label = None
        for shortcut, cfg in self.settings.get('shortcuts', {}).items():
            self.add_my_shortcut_row(self.my_shortcuts_frame, shortcut, cfg)
        if not self.settings.get('shortcuts'):
            self.my_empty_label = ctk.CTkLabel(
                self.my_shortcuts_frame,
                text="还没有自定义快捷键\n点击上方「录制新快捷键」添加",
                text_color='gray')
            self.my_empty_label.pack(pady=40)

    def add_my_shortcut_row(self, parent, shortcut, cfg):
        if self.my_empty_label:
            try:
                self.my_empty_label.destroy()
            except Exception:
                pass
            self.my_empty_label = None

        row = ctk.CTkFrame(parent, fg_color='#242430', corner_radius=8)
        row.pack(fill='x', pady=3)
        row.grid_columnconfigure(2, weight=1)

        enabled_var = tk.BooleanVar(value=cfg.get('enabled', True))
        ctk.CTkCheckBox(row, text='', width=36,
                        variable=enabled_var).grid(row=0, column=0, padx=(10, 2), pady=8)
        ctk.CTkLabel(row, text=shortcut, width=190,
                     font=ctk.CTkFont(size=13, weight='bold')).grid(
            row=0, column=1, padx=8, pady=8)
        display_var = tk.StringVar(value=cfg.get('display', shortcut.upper()))
        ctk.CTkEntry(row, textvariable=display_var, height=30).grid(
            row=0, column=2, sticky='ew', padx=8, pady=8)
        ctk.CTkButton(
            row, text="删除", width=64, height=30,
            fg_color='#5A2B2B', hover_color='#7A3A3A',
            command=lambda s=shortcut, r=row: self.delete_my_shortcut(s, r)
        ).grid(row=0, column=3, padx=(8, 10), pady=8)

        self.shortcut_rows[shortcut] = {
            'enabled_var': enabled_var,
            'display_var': display_var,
            'row_frame': row,
        }

    def delete_my_shortcut(self, shortcut, row_frame):
        if messagebox.askyesno("确认", f"确定要删除 {shortcut} 吗？"):
            self.settings['shortcuts'].pop(shortcut, None)
            self.shortcut_rows.pop(shortcut, None)
            row_frame.destroy()
            if not self.shortcut_rows:
                self.my_empty_label = ctk.CTkLabel(
                    self.my_shortcuts_frame,
                    text="还没有自定义快捷键\n点击上方「录制新快捷键」添加",
                    text_color='gray')
                self.my_empty_label.pack(pady=40)

    def capture_new_shortcut(self):
        self.capture_active = True
        self.update_suspend()
        self.capture_dialog = KeyCaptureDialog(
            self.settings_window,
            on_capture=self.on_shortcut_captured,
            on_cancel=self.on_capture_canceled)
        self.capture_dialog.show()

    def on_shortcut_captured(self, shortcut):
        self.capture_dialog = None
        self.capture_active = False
        self.update_suspend()

        if shortcut in self.settings['shortcuts']:
            messagebox.showwarning("提示", f"快捷键 {shortcut} 已存在")
            return
        try:
            keyboard.parse_hotkey(shortcut)
        except Exception as e:
            messagebox.showerror(
                "无法识别", f"无法识别按键组合 {shortcut}\n请重新录制。\n({e})")
            return

        display = self.format_display_name(shortcut)
        self.settings['shortcuts'][shortcut] = {
            'enabled': True,
            'display': display,
        }
        if self.my_shortcuts_frame:
            self.add_my_shortcut_row(
                self.my_shortcuts_frame, shortcut,
                self.settings['shortcuts'][shortcut])
        messagebox.showinfo("成功", f"已添加 {display}\n点击“保存”后生效")

    def on_capture_canceled(self):
        self.capture_dialog = None
        self.capture_active = False
        self.update_suspend()

    def format_display_name(self, shortcut):
        parts = shortcut.split('+')
        return '+'.join(
            DISPLAY_NAME_MAP.get(p, p.upper() if len(p) == 1 else p.capitalize())
            for p in parts)

    # ---------- 软件预设页 ----------

    def build_presets_tab(self, parent):
        top = ctk.CTkFrame(parent, fg_color='transparent')
        top.pack(fill='x', padx=12, pady=(12, 4))

        self.presets_search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(
            top, textvariable=self.presets_search_var,
            placeholder_text="搜索预设名称 / 分类 / 快捷键...",
            width=300, height=34)
        search_entry.pack(side='left', padx=(0, 12))
        search_entry.bind('<KeyRelease>', self._on_presets_search_key)

        self.auto_mode_var = tk.BooleanVar(
            value=bool(self.settings.get('auto_mode')))
        ctk.CTkSwitch(
            top, text="自动模式", variable=self.auto_mode_var,
            command=self._on_auto_mode_toggle).pack(side='right')
        ctk.CTkLabel(
            top, text="开启后自动检测当前软件，启用对应预设",
            text_color='gray').pack(side='right', padx=10)

        self.presets_frame = ctk.CTkScrollableFrame(
            parent, fg_color='transparent')
        self.presets_frame.pack(fill='both', expand=True, padx=12, pady=10)
        # 延迟构建预设卡片，避免设置窗口打开时卡顿
        self.preset_cards = {}
        self.preset_count_labels = {}
        self.preset_row_vars = {}
        self.root.after(250, self.rebuild_presets_list)

    def _on_presets_search_key(self, event):
        """搜索输入防抖：停止输入 200ms 后再重建列表"""
        if self.presets_search_after:
            try:
                self.root.after_cancel(self.presets_search_after)
            except Exception:
                pass
        self.presets_search_after = self.root.after(
            200, self.rebuild_presets_list)

    def _on_auto_mode_toggle(self):
        want = bool(self.auto_mode_var.get())
        if want and not self._confirm_auto_mode_enable():
            # 用户取消：回退开关
            self.auto_mode_var.set(False)
            return
        if want and self.continuous_mode:
            self._set_continuous_mode(False)
        self.settings['auto_mode'] = want
        # 自动模式为会话级设置，不写入设置文件（每次启动默认关闭）
        self.refresh_foreground_match()
        self.refresh_tray_menu()

    def _on_continuous_mode_toggle(self):
        want = bool(self.continuous_mode_var.get())
        if want and not self._confirm_continuous_mode_enable():
            self.continuous_mode_var.set(False)
            return
        self._set_continuous_mode(want)
        self.refresh_tray_menu()

    def tray_toggle_continuous_mode(self, icon, item):
        self.root.after(0, self._toggle_continuous_mode_from_tray)

    def _toggle_continuous_mode_from_tray(self):
        want = not self.continuous_mode
        if want and not self._confirm_continuous_mode_enable():
            return
        self._set_continuous_mode(want)
        self.refresh_tray_menu()

    def _confirm_continuous_mode_enable(self):
        return messagebox.askokcancel(
            "持续输出模式声明",
            "开启持续输出模式后：\n\n"
            "· 停用原有的“按下组合键后显示”方式；\n"
            "· 自动模式将被关闭。\n\n"
            "开启后，按下 Ctrl/Shift/Alt/Win 会立即显示，"
            "并追加后续按键与点击次数。\n\n是否开启？",
            icon='info')

    def _set_continuous_mode(self, enabled):
        self.continuous_mode = enabled
        self.settings['continuous_mode'] = enabled
        if enabled:
            # 停用自动模式
            self.settings['auto_mode'] = False
            self.matched_preset_ids = set()
            if hasattr(self, 'auto_mode_var'):
                try:
                    self.auto_mode_var.set(False)
                except Exception:
                    pass
        self.cont_pressed.clear()
        self.cont_keys = []
        self.cont_count = 1
        self.cont_active = False
        if hasattr(self, 'continuous_mode_var'):
            try:
                self.continuous_mode_var.set(enabled)
            except Exception:
                pass
        self.settings_manager.save_settings()
        self.refresh_foreground_match()
        self.refresh_tray_menu()

    def _confirm_auto_mode_enable(self):
        """开启自动模式前的免责声明，同意返回 True"""
        return messagebox.askokcancel(
            "自动模式免责声明",
            "开启自动模式后，程序会持续检测当前前台窗口，"
            "用于自动匹配对应软件的快捷键预设。\n\n"
            "检测完全在本机进行，不会上传或保存任何窗口信息。\n\n"
            "是否开启自动模式？",
            icon='info')

    def preset_matches_query(self, preset, query):
        if query in preset['name'].lower() or query in preset['category'].lower():
            return True
        if query in (preset.get('description') or '').lower():
            return True
        for sc, cfg in preset['shortcuts'].items():
            if query in sc.lower():
                return True
            if query in (cfg.get('display') or '').lower():
                return True
        return False

    def rebuild_presets_list(self):
        if not self.presets_frame:
            return
        for w in self.presets_frame.winfo_children():
            w.destroy()
        self.preset_cards = {}
        self.preset_count_labels = {}
        self.preset_row_vars = {}
        self.preset_display_vars = {}
        self.preset_bodies = {}
        self.preset_expand_buttons = {}
        query = ''
        if self.presets_search_var:
            query = self.presets_search_var.get().strip().lower()
        shown = 0
        for pid in PRESET_ORDER:
            preset = PRESET_LIBRARY.get(pid)
            if not preset:
                continue
            if query and not self.preset_matches_query(preset, query):
                continue
            self.add_preset_card(self.presets_frame, pid)
            shown += 1
        if shown == 0:
            ctk.CTkLabel(
                self.presets_frame, text="没有找到匹配的预设",
                text_color='gray').pack(pady=30)

    def add_preset_card(self, parent, pid):
        preset = PRESET_LIBRARY[pid]
        state = self.settings['preset_states'].setdefault(
            pid, {'enabled': pid == 'windows', 'shortcuts': {}})
        overrides = state.setdefault('shortcuts', {})
        total = len(preset['shortcuts'])
        disabled_count = sum(
            1 for sc in preset['shortcuts']
            if overrides.get(sc, {}).get('enabled') is False)
        enabled_count = total - disabled_count

        card = ctk.CTkFrame(parent, corner_radius=10)
        card.pack(fill='x', pady=4)
        self.preset_cards[pid] = card

        head = ctk.CTkFrame(card, fg_color='transparent')
        head.pack(fill='x', padx=12, pady=8)
        head.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            head, text=preset['category'], width=76, height=24,
            corner_radius=12, fg_color='#2B3A55', text_color='#A8C8FF',
            font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky='w')
        ctk.CTkLabel(
            head, text=preset['name'], anchor='w',
            font=ctk.CTkFont(size=14, weight='bold')).grid(
            row=0, column=1, sticky='w', padx=(10, 8))
        count_label = ctk.CTkLabel(
            head, text=f"已启用 {enabled_count}/{total}",
            text_color='gray')
        count_label.grid(row=0, column=2, padx=(0, 10))
        self.preset_count_labels[pid] = count_label

        expand_var = tk.BooleanVar(value=pid in self.expanded_presets)
        switch_var = tk.BooleanVar(value=bool(state.get('enabled')))
        self.preset_switch_vars[pid] = switch_var
        ctk.CTkSwitch(
            head, text="启用", width=52,
            variable=switch_var,
            command=lambda p=pid: self.on_preset_enabled_toggle(p)).grid(
            row=0, column=3, padx=(0, 8))
        expand_btn = ctk.CTkButton(
            head, text="收起 ▴" if pid in self.expanded_presets else "展开 ▾",
            width=70, height=28, fg_color='#3A3A3C', hover_color='#4A4A4C',
            command=lambda: self.toggle_preset_expand(pid))
        expand_btn.grid(row=0, column=4)
        self.preset_expand_buttons[pid] = expand_btn

        if pid in self.expanded_presets:
            self.add_preset_card_body(card, pid)

    def add_preset_card_body(self, card, pid):
        """为预设卡片创建展开内容（只影响这一张卡片）"""
        preset = PRESET_LIBRARY[pid]
        body = ctk.CTkFrame(card, fg_color='transparent')
        body.pack(fill='x', padx=14, pady=(0, 10))
        self.preset_bodies[pid] = body

        ctk.CTkLabel(body, text=preset.get('description') or '',
                     text_color='gray', justify='left').pack(
            anchor='w', pady=(0, 6))

        for sc, cfg in preset['shortcuts'].items():
            self.add_preset_shortcut_row(body, pid, sc, cfg)

        op_frame = ctk.CTkFrame(body, fg_color='transparent')
        op_frame.pack(fill='x', pady=(8, 0))
        ctk.CTkButton(
            op_frame, text="全部启用", width=80, height=26,
            fg_color='#2B3A55', hover_color='#3A4A6A',
            command=lambda: self.preset_bulk_enable(pid)).pack(side='left', padx=4)
        ctk.CTkButton(
            op_frame, text="全部禁用", width=80, height=26,
            fg_color='#3A3A3C', hover_color='#4A4A4C',
            command=lambda: self.preset_bulk_disable(pid)).pack(side='left', padx=4)
        ctk.CTkButton(
            op_frame, text="恢复默认", width=80, height=26,
            fg_color='#3A3A3C', hover_color='#4A4A4C',
            command=lambda: self.preset_reset(pid)).pack(side='left', padx=4)

    def toggle_preset_expand(self, pid):
        if pid in self.expanded_presets:
            self.expanded_presets.discard(pid)
            body = self.preset_bodies.pop(pid, None)
            if body:
                try:
                    body.destroy()
                except Exception:
                    pass
        else:
            self.expanded_presets.add(pid)
            card = self.preset_cards.get(pid)
            if card:
                self.add_preset_card_body(card, pid)
        btn = self.preset_expand_buttons.get(pid)
        if btn:
            btn.configure(
                text="收起 ▴" if pid in self.expanded_presets else "展开 ▾")

    def on_preset_enabled_toggle(self, pid):
        state = self.settings['preset_states'].setdefault(
            pid, {'enabled': False, 'shortcuts': {}})
        var = self.preset_switch_vars.get(pid)
        if var is not None:
            state['enabled'] = bool(var.get())

    def add_preset_shortcut_row(self, parent, pid, sc, cfg):
        state = self.settings['preset_states'].setdefault(
            pid, {'enabled': False, 'shortcuts': {}})
        overrides = state.setdefault('shortcuts', {})
        ov = overrides.get(sc, {})

        # 设置界面里手写的 tk 控件不自动缩放，需按 DPI 系数放大字号
        row_font = max(9, int(12 * self.font_scale))

        row = tk.Frame(parent, bg='#1E1E28')
        row.pack(fill='x', pady=2)
        row.grid_columnconfigure(2, weight=1)

        enabled = ov.get('enabled', True) is not False
        enabled_var = tk.BooleanVar(value=enabled)
        self.preset_row_vars[(pid, sc)] = enabled_var

        def on_enable_change(p=pid, s=sc, var=enabled_var):
            overrides = self.settings['preset_states'].setdefault(
                p, {'enabled': False, 'shortcuts': {}})['shortcuts']
            if var.get():
                overrides.setdefault(s, {}).pop('enabled', None)
            else:
                overrides.setdefault(s, {})['enabled'] = False
            self._update_preset_count(p)

        tk.Checkbutton(
            row, variable=enabled_var, command=on_enable_change,
            bg='#1E1E28', fg='#E1E1E1', activebackground='#1E1E28',
            activeforeground='#E1E1E1', selectcolor='#2D2B3E',
            highlightthickness=0, bd=0,
            font=('Microsoft YaHei', row_font)).grid(
            row=0, column=0, padx=(8, 2), pady=5)
        tk.Label(
            row, text=sc, width=24, anchor='w', bg='#1E1E28', fg='#E1E1E1',
            font=('Microsoft YaHei', row_font, 'bold')).grid(
            row=0, column=1, padx=6, pady=5)

        display_var = tk.StringVar(value=ov.get('display') or cfg.get('display') or sc)

        def on_display_change(p=pid, s=sc, var=display_var):
            overrides = self.settings['preset_states'].setdefault(
                p, {'enabled': False, 'shortcuts': {}})['shortcuts']
            overrides.setdefault(s, {})['display'] = var.get()

        display_var.trace_add('write', lambda *_: on_display_change())
        tk.Entry(
            row, textvariable=display_var, bg='#2D2B3E', fg='#E1E1E1',
            insertbackground='#E1E1E1', relief='flat',
            highlightthickness=1, highlightbackground='#3A3A4C',
            highlightcolor='#4A6A9A',
            font=('Microsoft YaHei', row_font)).grid(
            row=0, column=2, sticky='ew', padx=6, pady=5)
        self.preset_display_vars[(pid, sc)] = display_var

        def on_reset(p=pid, s=sc):
            overrides = self.settings['preset_states'].setdefault(
                p, {'enabled': False, 'shortcuts': {}})['shortcuts']
            overrides.pop(s, None)
            var = self.preset_row_vars.get((p, s))
            if var:
                var.set(True)
            dvar = self.preset_display_vars.get((p, s))
            if dvar:
                dvar.set(PRESET_LIBRARY[p]['shortcuts'][s].get(
                    'display') or s)
            self._update_preset_count(p)

        tk.Button(
            row, text="↺", width=4, bg='#3A3A3C', fg='#E1E1E1',
            activebackground='#4A4A4C', activeforeground='#E1E1E1',
            relief='flat', bd=0, command=on_reset,
            font=('Microsoft YaHei', row_font)).grid(
            row=0, column=3, padx=(6, 8), pady=5)

    def preset_bulk_enable(self, pid):
        overrides = self.settings['preset_states'].setdefault(
            pid, {'enabled': False, 'shortcuts': {}})['shortcuts']
        for sc in PRESET_LIBRARY[pid]['shortcuts']:
            ov = overrides.get(sc)
            if ov:
                ov.pop('enabled', None)
                if not ov:
                    overrides.pop(sc, None)
            var = self.preset_row_vars.get((pid, sc))
            if var:
                var.set(True)
        self._update_preset_count(pid)

    def preset_bulk_disable(self, pid):
        overrides = self.settings['preset_states'].setdefault(
            pid, {'enabled': False, 'shortcuts': {}})['shortcuts']
        for sc in PRESET_LIBRARY[pid]['shortcuts']:
            overrides.setdefault(sc, {})['enabled'] = False
            var = self.preset_row_vars.get((pid, sc))
            if var:
                var.set(False)
        self._update_preset_count(pid)

    def preset_reset(self, pid):
        state = self.settings['preset_states'].setdefault(
            pid, {'enabled': False, 'shortcuts': {}})
        state['shortcuts'] = {}
        for sc in PRESET_LIBRARY[pid]['shortcuts']:
            var = self.preset_row_vars.get((pid, sc))
            if var:
                var.set(True)
            dvar = self.preset_display_vars.get((pid, sc))
            if dvar:
                dvar.set(PRESET_LIBRARY[pid]['shortcuts'][sc].get(
                    'display') or sc)
        self._update_preset_count(pid)

    def _update_preset_count(self, pid):
        """局部更新某张卡片的已启用数量（不重建界面）"""
        label = self.preset_count_labels.get(pid)
        preset = PRESET_LIBRARY.get(pid)
        if not label or not preset:
            return
        state = self.settings['preset_states'].setdefault(
            pid, {'enabled': False, 'shortcuts': {}})
        overrides = state.setdefault('shortcuts', {})
        total = len(preset['shortcuts'])
        disabled = sum(
            1 for sc in preset['shortcuts']
            if overrides.get(sc, {}).get('enabled') is False)
        label.configure(text=f"已启用 {total - disabled}/{total}")

    # ---------- 外观页 ----------

    def build_appearance_tab(self, parent):
        frame = ctk.CTkScrollableFrame(parent, fg_color='transparent')
        frame.pack(fill='both', expand=True, padx=12, pady=12)
        frame.columnconfigure(1, weight=1)
        ap = self.settings['appearance']

        preview_box = ctk.CTkFrame(frame, corner_radius=10)
        preview_box.grid(row=0, column=0, columnspan=3,
                         padx=6, pady=(0, 12), sticky='ew')
        self.preview_canvas = tk.Canvas(
            preview_box, width=430, height=86,
            highlightthickness=0, bg='#14141C')
        self.preview_canvas.pack(padx=10, pady=10, fill='x')
        self.preview_label = ctk.CTkLabel(frame, text="实时预览")
        self.preview_label.grid(row=0, column=3, padx=12, sticky='w')

        row = 1
        ctk.CTkLabel(frame, text="窗口透明度").grid(
            row=row, column=0, sticky='w', padx=6, pady=7)
        self.opacity_var = tk.DoubleVar(value=ap['window_opacity'])
        self.opacity_slider = ctk.CTkSlider(
            frame, from_=0.3, to=1.0, number_of_steps=14,
            variable=self.opacity_var, command=lambda v: self.update_preview())
        self.opacity_slider.grid(row=row, column=1, sticky='ew', padx=6, pady=7)
        self.opacity_pct_label = ctk.CTkLabel(frame, text="")
        self.opacity_pct_label.grid(row=row, column=2, padx=6)

        row += 1
        ctk.CTkLabel(frame, text="显示时长(秒)").grid(
            row=row, column=0, sticky='w', padx=6, pady=7)
        self.duration_var = tk.StringVar(value=str(ap['display_duration'] / 1000))
        ctk.CTkEntry(frame, textvariable=self.duration_var,
                     width=120).grid(row=row, column=1, sticky='w', padx=6, pady=7)

        row += 1
        ctk.CTkLabel(frame, text="淡出时长(秒)").grid(
            row=row, column=0, sticky='w', padx=6, pady=7)
        self.fade_duration_var = tk.StringVar(value=str(ap['fade_duration'] / 1000))
        ctk.CTkEntry(frame, textvariable=self.fade_duration_var,
                     width=120).grid(row=row, column=1, sticky='w', padx=6, pady=7)

        row += 1
        ctk.CTkLabel(frame, text="显示位置").grid(
            row=row, column=0, sticky='w', padx=6, pady=7)
        self.position_var = tk.StringVar(value=ap['position'])
        pos_frame = ctk.CTkFrame(frame, fg_color='transparent')
        pos_frame.grid(row=row, column=1, sticky='w', padx=6, pady=7)
        ctk.CTkOptionMenu(
            pos_frame, values=POSITIONS, width=170,
            variable=self.position_var,
            command=lambda v: self.update_preview()).pack(side='left')
        ctk.CTkButton(
            pos_frame, text="拖动定位", width=90, height=30,
            command=self.show_drag_hint).pack(side='left', padx=8)

        row += 1
        ctk.CTkLabel(frame, text="背景颜色").grid(
            row=row, column=0, sticky='w', padx=6, pady=7)
        self.bg_color_var = tk.StringVar(value=ap['bg_color'])
        ctk.CTkEntry(frame, textvariable=self.bg_color_var,
                     width=120).grid(row=row, column=1, sticky='w', padx=6, pady=7)
        ctk.CTkButton(
            frame, text="选择", width=70, height=30,
            command=lambda: self.choose_color(self.bg_color_var)).grid(
            row=row, column=2, sticky='w', padx=6)

        row += 1
        ctk.CTkLabel(frame, text="文字颜色").grid(
            row=row, column=0, sticky='w', padx=6, pady=7)
        self.text_color_var = tk.StringVar(value=ap['text_color'])
        ctk.CTkEntry(frame, textvariable=self.text_color_var,
                     width=120).grid(row=row, column=1, sticky='w', padx=6, pady=7)
        ctk.CTkButton(
            frame, text="选择", width=70, height=30,
            command=lambda: self.choose_color(self.text_color_var)).grid(
            row=row, column=2, sticky='w', padx=6)

        row += 1
        ctk.CTkLabel(frame, text="边框颜色").grid(
            row=row, column=0, sticky='w', padx=6, pady=7)
        self.border_color_var = tk.StringVar(value=ap['border_color'])
        ctk.CTkEntry(frame, textvariable=self.border_color_var,
                     width=120).grid(row=row, column=1, sticky='w', padx=6, pady=7)
        ctk.CTkButton(
            frame, text="选择", width=70, height=30,
            command=lambda: self.choose_color(self.border_color_var)).grid(
            row=row, column=2, sticky='w', padx=6)

        row += 1
        ctk.CTkLabel(frame, text="字体大小").grid(
            row=row, column=0, sticky='w', padx=6, pady=7)
        self.font_size_var = tk.StringVar(value=str(ap['font_size']))
        ctk.CTkEntry(frame, textvariable=self.font_size_var,
                     width=120).grid(row=row, column=1, sticky='w', padx=6, pady=7)

        row += 1
        ctk.CTkLabel(frame, text="提示框宽度(px)").grid(
            row=row, column=0, sticky='w', padx=6, pady=7)
        self.width_override_var = tk.StringVar(
            value=str(int(ap.get('width_override') or 0)))
        ctk.CTkEntry(frame, textvariable=self.width_override_var,
                     width=120).grid(
            row=row, column=1, sticky='w', padx=6, pady=7)
        ctk.CTkLabel(frame, text="0 = 按内容自动",
                     text_color='gray').grid(
            row=row, column=2, sticky='w', padx=6)

        row += 1
        ctk.CTkLabel(frame, text="提示框高度(px)").grid(
            row=row, column=0, sticky='w', padx=6, pady=7)
        self.height_override_var = tk.StringVar(
            value=str(int(ap.get('height_override') or 0)))
        ctk.CTkEntry(frame, textvariable=self.height_override_var,
                     width=120).grid(
            row=row, column=1, sticky='w', padx=6, pady=7)
        ctk.CTkLabel(frame, text="0 = 按字体自动",
                     text_color='gray').grid(
            row=row, column=2, sticky='w', padx=6)

        for var in [self.duration_var, self.fade_duration_var,
                    self.bg_color_var, self.text_color_var,
                    self.border_color_var, self.font_size_var,
                    self.width_override_var, self.height_override_var]:
            var.trace_add('write', lambda *_: self.update_preview())
        self.update_preview()

    def choose_color(self, color_var):
        color = colorchooser.askcolor(color=color_var.get(), title="选择颜色")
        if color and color[1]:
            color_var.set(color[1])

    def update_preview(self):
        try:
            if not self.preview_canvas or not self.preview_canvas.winfo_exists():
                return
            self.preview_canvas.delete('all')
            bg = self.bg_color_var.get().strip()
            text = self.text_color_var.get().strip()
            border = self.border_color_var.get().strip()
            try:
                size = int(self.font_size_var.get())
            except Exception:
                size = 12
            try:
                opacity = float(self.opacity_var.get())
            except Exception:
                opacity = 0.75
            try:
                width_ov = int(self.width_override_var.get())
            except Exception:
                width_ov = 0
            try:
                height_ov = int(self.height_override_var.get())
            except Exception:
                height_ov = 0
            self.opacity_pct_label.config(text=f"{int(opacity * 100)}%")
            if width_ov > 0 and height_ov > 0:
                size_hint = f"固定 {width_ov}×{height_ov}"
            elif width_ov > 0:
                size_hint = f"固定宽度 {width_ov}px"
            elif height_ov > 0:
                size_hint = f"固定高度 {height_ov}px"
            else:
                size_hint = "自动尺寸"
            self.preview_label.config(text=f"实时预览 · {size_hint}")

            if not (is_valid_color(bg) and is_valid_color(text)
                    and is_valid_color(border)):
                self.preview_canvas.create_text(
                    215, 45, text="颜色需为 #RRGGBB 格式",
                    fill='#888888', font=('Microsoft YaHei', 10))
                return

            w, h, x, y = 410, 62, 10, 12
            self.preview_canvas.create_polygon(
                offset_points(rounded_rect_points(w, h, 8, 1), x, y),
                smooth=True, fill=border)
            self.preview_canvas.create_polygon(
                offset_points(rounded_rect_points(w, h, 8, 0), x, y),
                smooth=True, fill=bg)
            self.preview_canvas.create_text(
                x + w // 2, y + h // 2,
                text=f"预览 {size}pt",
                font=('Microsoft YaHei', size, 'bold'),
                fill=text)
        except Exception as e:
            safe_log(f"预览更新失败: {e}")

    # ---------- 系统页 ----------

    def build_system_tab(self, parent):
        # 用可滚动容器：窗口较小时关于项等也能滚动查看
        frame = ctk.CTkScrollableFrame(parent, fg_color='transparent')
        frame.pack(fill='both', expand=True, padx=12, pady=12)

        card = ctk.CTkFrame(frame, corner_radius=10)
        card.pack(fill='x', pady=6)
        ctk.CTkLabel(
            card, text="开机自启", font=ctk.CTkFont(size=15, weight='bold'),
            anchor='w').pack(fill='x', padx=16, pady=(14, 0))
        ctk.CTkLabel(
            card, text="登录 Windows 后自动运行本程序（注册表 + 启动文件夹双保险）",
            text_color='gray', anchor='w', justify='left').pack(
            fill='x', padx=16, pady=(4, 12))
        self.autostart_var = tk.BooleanVar(
            value=bool(self.settings.get('autostart', False))
            or self.check_autostart())
        ctk.CTkSwitch(
            card, text="开机自动启动", variable=self.autostart_var,
            command=lambda: self._set_autostart(self.autostart_var.get())
        ).pack(anchor='w', padx=16, pady=(0, 14))

        card2 = ctk.CTkFrame(frame, corner_radius=10)
        card2.pack(fill='x', pady=6)
        ctk.CTkLabel(
            card2, text="自动模式", font=ctk.CTkFont(size=15, weight='bold'),
            anchor='w').pack(fill='x', padx=16, pady=(14, 0))
        ctk.CTkLabel(
            card2, text="自动模式开关位于「软件预设」页顶部。\n开启后程序每秒检测一次前台窗口，"
                        "自动启用对应软件的快捷键预设；切换到没有预设的软件时自动回到已手动启用的预设。",
            text_color='gray', anchor='w', justify='left').pack(
            fill='x', padx=16, pady=(4, 14))
        ctk.CTkLabel(
            card2, text="注意：调出任务管理器（尤其是以管理员权限运行时）可能导致按键提示暂时失效"
                        "或显示异常；关闭任务管理器后会自动恢复，如仍异常可重启程序。",
            text_color='#C9A86A', anchor='w', justify='left',
            font=ctk.CTkFont(size=13)).pack(
            fill='x', padx=16, pady=(0, 14))

        card_cont = ctk.CTkFrame(frame, corner_radius=10)
        card_cont.pack(fill='x', pady=6)
        ctk.CTkLabel(
            card_cont, text="持续输出模式",
            font=ctk.CTkFont(size=15, weight='bold'),
            anchor='w').pack(fill='x', padx=16, pady=(14, 0))
        ctk.CTkLabel(
            card_cont, text="开启后停用原有提示方式与自动模式：按下 Ctrl/Shift/Alt/Win 立即显示，"
                        "并追加后续按键与点击次数。适合需要实时看到自己键位操作的用户。",
            text_color='gray', anchor='w', justify='left').pack(
            fill='x', padx=16, pady=(4, 12))
        self.continuous_mode_var = tk.BooleanVar(value=bool(self.continuous_mode))
        ctk.CTkSwitch(
            card_cont, text="开启持续输出模式",
            variable=self.continuous_mode_var,
            command=self._on_continuous_mode_toggle
        ).pack(anchor='w', padx=16, pady=(0, 14))

        card3 = ctk.CTkFrame(frame, corner_radius=10)
        card3.pack(fill='x', pady=6)
        ctk.CTkLabel(
            card3, text="其他", font=ctk.CTkFont(size=15, weight='bold'),
            anchor='w').pack(fill='x', padx=16, pady=(14, 0))
        ctk.CTkLabel(
            card3, text=f"设置文件：{self.settings_manager.settings_file}",
            text_color='gray', anchor='w', justify='left').pack(
            fill='x', padx=16, pady=(4, 4))
        ctk.CTkLabel(
            card3, text="如需彻底重置，可删除上方设置文件后重启程序。",
            text_color='gray', anchor='w', justify='left').pack(
            fill='x', padx=16, pady=(0, 14))

        card4 = ctk.CTkFrame(frame, corner_radius=10)
        card4.pack(fill='x', pady=6)
        ctk.CTkLabel(
            card4, text="关于", font=ctk.CTkFont(size=15, weight='bold'),
            anchor='w').pack(fill='x', padx=16, pady=(14, 0))
        about_rows = [
            ("软件名", f"{APP_NAME}"),
            ("开发者", "Michael2070"),
            ("开发环境", "Windows / Python 3.13 + Tkinter（CustomTkinter）"),
            ("AI 模型", "GPT-5（Codex）"),
        ]
        about_frame = ctk.CTkFrame(card4, fg_color='transparent')
        about_frame.pack(fill='x', padx=16, pady=(4, 14))
        for label, value in about_rows:
            row = ctk.CTkFrame(about_frame, fg_color='transparent')
            row.pack(fill='x', pady=2)
            ctk.CTkLabel(row, text=label, width=90, anchor='w',
                         text_color='gray').pack(side='left')
            ctk.CTkLabel(row, text=value, anchor='w').pack(side='left')

    # ---------- 保存 / 取消 ----------

    def apply_settings(self):
        try:
            opacity = float(self.opacity_var.get())
            duration = float(self.duration_var.get())
            fade = float(self.fade_duration_var.get())
            position = self.position_var.get().strip()
            bg = self.bg_color_var.get().strip()
            text = self.text_color_var.get().strip()
            border = self.border_color_var.get().strip()
            font_size = int(self.font_size_var.get())
            width_override = int(self.width_override_var.get().strip() or '0')
            height_override = int(self.height_override_var.get().strip() or '0')
        except Exception:
            messagebox.showerror("设置无效", "请检查填写的内容是否为有效数值")
            return

        errors = []
        if not 0.3 <= opacity <= 1.0:
            errors.append("透明度应在 0.3 ~ 1.0 之间")
        if not 0.5 <= duration <= 10:
            errors.append("显示时长应在 0.5 ~ 10 秒之间")
        if not 0.1 <= fade <= 3:
            errors.append("淡出时长应在 0.1 ~ 3 秒之间")
        if position not in POSITIONS:
            errors.append("请选择有效的显示位置")
        for name, value in [("背景颜色", bg), ("文字颜色", text), ("边框颜色", border)]:
            if not is_valid_color(value):
                errors.append(f"{name}格式应为 #RRGGBB，例如 #2D2B3E")
        if not 8 <= font_size <= 32:
            errors.append("字体大小应在 8 ~ 32 之间")
        if width_override != 0 and not 80 <= width_override <= 2000:
            errors.append("提示框宽度需为 0(自动) 或 80 ~ 2000 像素")
        if height_override != 0 and not 30 <= height_override <= 600:
            errors.append("提示框高度需为 0(自动) 或 30 ~ 600 像素")
        if errors:
            messagebox.showerror("设置无效", "\n".join(errors))
            return

        # 同步我的快捷键行
        for shortcut, row in list(self.shortcut_rows.items()):
            if shortcut in self.settings['shortcuts']:
                self.settings['shortcuts'][shortcut]['enabled'] = \
                    row['enabled_var'].get()
                display = row['display_var'].get().strip()
                self.settings['shortcuts'][shortcut]['display'] = \
                    display or shortcut

        # 自动模式
        self.settings['auto_mode'] = bool(self.auto_mode_var.get())

        ap = self.settings['appearance']
        ap['window_opacity'] = round(opacity, 2)
        ap['display_duration'] = int(duration * 1000)
        ap['fade_duration'] = int(fade * 1000)
        ap['position'] = position
        ap['bg_color'] = bg.upper()
        ap['text_color'] = text.upper()
        ap['border_color'] = border.upper()
        ap['font_size'] = font_size
        ap['width_override'] = width_override
        ap['height_override'] = height_override

        if not self.settings_manager.save_settings():
            messagebox.showerror("错误", "保存设置失败，请检查文件写入权限")
            return

        self.display_duration = ap['display_duration']
        self.fade_duration = ap['fade_duration']
        self.fade_alpha = ap['window_opacity']
        if self.window:
            self.update_window_content()

        self.refresh_foreground_match()
        self.sync_hotkeys()
        self.close_settings_window()
        messagebox.showinfo("成功", "设置已保存并生效")

    def cancel_settings(self):
        if self.capture_dialog:
            try:
                self.capture_dialog.cancel()
            except Exception:
                pass
        self.settings = copy.deepcopy(self.settings_snapshot)
        self.settings_manager.settings = self.settings
        self.close_settings_window()

    def close_settings_window(self):
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
        self.settings_window = None
        self.update_suspend()

    # ---------- 开机自启 ----------

    def get_autostart_command(self):
        if getattr(sys, 'frozen', False):
            return f'"{sys.executable}"'
        script_path = os.path.abspath(sys.argv[0])
        pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
        exe = pythonw if os.path.exists(pythonw) else sys.executable
        return f'"{exe}" "{script_path}"'

    def get_startup_autostart_file(self):
        appdata = os.environ.get('APPDATA', '')
        if not appdata:
            return None
        return os.path.join(
            appdata, r'Microsoft\Windows\Start Menu\Programs\Startup',
            AUTOSTART_NAME + '.bat')

    def add_registry_autostart(self):
        try:
            key = winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, AUTOSTART_REG_PATH,
                0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(
                key, AUTOSTART_NAME, 0, winreg.REG_SZ,
                self.get_autostart_command())
            winreg.CloseKey(key)
            return True
        except Exception as e:
            safe_log(f"注册表自启写入失败: {e}")
            return False

    def add_startup_folder_autostart(self):
        """备用方案：在启动文件夹创建启动批处理"""
        bat_path = self.get_startup_autostart_file()
        if not bat_path:
            return False, "找不到启动文件夹"
        try:
            if getattr(sys, 'frozen', False):
                target = sys.executable
                content = f'@echo off\r\nstart "" "{target}"\r\n'
            else:
                target = os.path.join(
                    os.path.dirname(sys.executable), 'pythonw.exe')
                if not os.path.exists(target):
                    target = sys.executable
                script_path = os.path.abspath(sys.argv[0])
                content = (
                    f'@echo off\r\nstart "" "{target}" "{script_path}"\r\n')
            os.makedirs(os.path.dirname(bat_path), exist_ok=True)
            with open(bat_path, 'w', encoding='gbk', errors='replace') as f:
                f.write(content)
            return True, None
        except Exception as e:
            return False, str(e)

    def add_autostart(self):
        if self.add_registry_autostart():
            return True, None
        ok, msg = self.add_startup_folder_autostart()
        if ok:
            return True, None
        return False, f"注册表写入失败，备用方案也失败：{msg}"

    def remove_autostart(self):
        removed_any = False
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, AUTOSTART_REG_PATH,
                0, winreg.KEY_SET_VALUE)
            try:
                winreg.DeleteValue(key, AUTOSTART_NAME)
                removed_any = True
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass
        except Exception as e:
            safe_log(f"删除注册表自启失败: {e}")
        bat_path = self.get_startup_autostart_file()
        if bat_path and os.path.exists(bat_path):
            try:
                os.remove(bat_path)
                removed_any = True
            except Exception as e:
                safe_log(f"删除启动批处理失败: {e}")
        return removed_any

    def check_autostart(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, AUTOSTART_REG_PATH,
                0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, AUTOSTART_NAME)
                return True
            except FileNotFoundError:
                pass
            finally:
                winreg.CloseKey(key)
        except FileNotFoundError:
            pass
        except Exception:
            pass
        bat_path = self.get_startup_autostart_file()
        return bool(bat_path and os.path.exists(bat_path))

    def _set_autostart(self, enabled):
        if enabled:
            ok, err = self.add_autostart()
            msg = "已开启开机自启" if ok else f"开启失败：{err}"
        else:
            ok = self.remove_autostart()
            msg = "已关闭开机自启" if ok else "关闭开机自启失败"
        if ok:
            messagebox.showinfo("开机自启", msg)
        else:
            messagebox.showerror("开机自启", msg)
        self.settings['autostart'] = bool(ok)
        self.settings_manager.save_settings()
        current = self.settings.get('autostart', False) or self.check_autostart()
        if hasattr(self, 'autostart_var'):
            try:
                self.autostart_var.set(current)
            except Exception:
                pass

    def _ensure_autostart(self):
        """首次运行（默认开启自启）时确保注册表/启动项真正写入"""
        try:
            if not self.settings.get('autostart'):
                return
            if self.check_autostart():
                return
            ok, err = self.add_autostart()
            if not ok:
                self.settings['autostart'] = False
                self.settings_manager.save_settings()
                safe_log(f"开机自启设置失败: {err}")
                if self.tray_icon:
                    try:
                        self.tray_icon.notify(
                            "开机自启设置失败，可在设置中重新开启", APP_NAME)
                    except Exception:
                        pass
        except Exception as e:
            safe_log(f"开机自启初始化异常: {e}")

    def tray_toggle_autostart(self, icon, item):
        self.root.after(
            0, lambda: self._set_autostart(not self.check_autostart()))

    # ---------- 托盘与启动 ----------

    def create_tray_icon(self):
        image = self.create_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem(
                '测试提示',
                lambda i, it: self.root.after(0, self.test_notification)),
            pystray.MenuItem(
                '设置',
                lambda i, it: self.root.after(0, self.open_settings)),
            pystray.MenuItem(
                '重启程序',
                lambda i, it: self.root.after(0, self.restart_program)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                '自动模式',
                self.tray_toggle_auto_mode,
                checked=lambda item: bool(self.settings.get('auto_mode'))),
            pystray.MenuItem(
                '持续输出模式',
                self.tray_toggle_continuous_mode,
                checked=lambda item: bool(self.continuous_mode)),
            pystray.MenuItem(
                '开机自启',
                self.tray_toggle_autostart,
                checked=lambda item: self.check_autostart()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                '退出',
                lambda i, it: self.root.after(0, self.quit_app)),
        )
        self.tray_icon = pystray.Icon(
            "shortcut_notifier", image, APP_NAME, menu)

    def refresh_tray_menu(self):
        """立即刷新托盘菜单的勾选状态"""
        try:
            if self.tray_icon:
                self.tray_icon.update_menu()
        except Exception:
            pass

    def create_tray_image(self):
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        bg = self.settings['appearance']['bg_color']
        draw.rounded_rectangle(
            [2, 2, 62, 62], radius=14, fill=bg,
            outline='#FFFFFF', width=2)
        key_color = '#ECF0F1'
        cols, rows, gap = 4, 3, 4
        kw = (size - 2 * gap * 2 - (cols - 1) * gap) // cols
        kh = (size - 2 * gap * 2 - (rows - 1) * gap) // rows
        for r in range(rows):
            for c in range(cols):
                x0 = gap * 2 + c * (kw + gap)
                y0 = gap * 2 + r * (kh + gap)
                draw.rounded_rectangle(
                    [x0, y0, x0 + kw, y0 + kh], radius=4, fill=key_color)
        draw.ellipse([46, 46, 58, 58], fill='#2ECC71',
                     outline='#FFFFFF', width=2)
        return image

    def test_notification(self):
        self._show_message("测试：快捷键提示功能正常", '__test__')

    def tray_toggle_auto_mode(self, icon, item):
        self.root.after(0, self._toggle_auto_mode)

    def _toggle_auto_mode(self):
        want = not self.settings.get('auto_mode')
        if want and not self._confirm_auto_mode_enable():
            return
        if want and self.continuous_mode:
            self._set_continuous_mode(False)
        self.settings['auto_mode'] = want
        self.refresh_foreground_match()
        if want:
            messagebox.showinfo("自动模式", "已开启自动模式：将跟随前台软件切换预设")
        else:
            messagebox.showinfo("自动模式", "已关闭自动模式")
        self.refresh_tray_menu()

    def show_startup_notice(self):
        try:
            self._show_message(f"{APP_NAME}已启动", '__startup__')
            if self.tray_icon:
                self.tray_icon.notify(
                    f"{APP_NAME}已启动，右键托盘图标可打开设置", APP_NAME)
            # 首次运行提示：任务管理器可能导致提示暂时失效（仅提示一次）
            if not self.settings.get('taskmgr_notice_shown'):
                self.root.after(
                    2000,
                    lambda: self._show_taskmgr_notice())
        except Exception as e:
            safe_log(f"启动提示失败: {e}")

    def _show_taskmgr_notice(self):
        try:
            self.settings['taskmgr_notice_shown'] = True
            self.settings_manager.save_settings()
            messagebox.showinfo(
                APP_NAME,
                "温馨提示：调出任务管理器（尤其是以管理员权限运行时）"
                "可能导致按键提示暂时失效或显示异常。\n\n"
                "关闭任务管理器后通常会自动恢复；如仍异常，"
                "可通过托盘菜单「重启程序」解决。")
        except Exception as e:
            safe_log(f"提示任务管理器说明失败: {e}")

    def quit_app(self):
        self.running = False
        self.listener_stop.set()
        self.listener_reload.set()
        self.clear_all_timers()
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        try:
            self.root.quit()
        except Exception:
            pass
        os._exit(0)

    def restart_program(self):
        """重启程序：先启动新进程再退出当前进程"""
        try:
            self.clear_all_timers()
            self.listener_stop.set()
            self.listener_reload.set()
            try:
                keyboard.unhook_all()
            except Exception:
                pass
            if self.tray_icon:
                try:
                    self.tray_icon.stop()
                except Exception:
                    pass
            # 先释放单实例互斥，否则新进程会误判为“程序已在运行”
            release_single_instance_mutex()
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable], shell=False)
            else:
                pythonw = os.path.join(
                    os.path.dirname(sys.executable), 'pythonw.exe')
                exe = pythonw if os.path.exists(pythonw) else sys.executable
                subprocess.Popen(
                    [exe, os.path.abspath(sys.argv[0])], shell=False)
            self.root.after(200, lambda: os._exit(0))
        except Exception as e:
            safe_log(f"重启失败: {e}")
            try:
                messagebox.showerror("错误", f"重启失败: {e}")
            except Exception:
                pass

    def hide_console(self):
        try:
            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                user32.ShowWindow(hwnd, 0)
        except Exception:
            pass

    def run(self):
        self.start_listener()
        self.create_tray_icon()
        try:
            tray_thread = threading.Thread(
                target=self.tray_icon.run, daemon=True)
            tray_thread.start()
        except Exception as e:
            safe_log(f"托盘启动失败: {e}")
        ForegroundWatcher(self).start()
        self.start_heartbeat()
        self.root.after(25, self._poll_key_events)
        # 首次运行：默认开启开机自启，确保注册表/启动项真正写入
        self.root.after(1200, self._ensure_autostart)
        self.root.after(1000, self.hide_console)
        self.root.after(600, self.show_startup_notice)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.quit_app()


if __name__ == "__main__":
    if not ensure_single_instance():
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(APP_NAME, "程序已在运行中，请查看系统托盘。")
            root.destroy()
        except Exception:
            pass
        sys.exit(0)
    notifier = ShortcutNotifier()
    notifier.run()
