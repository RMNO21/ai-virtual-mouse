import ctypes
import time

# Set high DPI awareness on Windows so coordinates match physical monitor pixels
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # Per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32

# Windows Mouse Event Constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120

class MouseController:
    """
    Ultra-low latency, native Windows mouse controller using Win32 API.
    Zero latency compared to pyautogui or pynput.
    """
    def __init__(self):
        self.screen_width = user32.GetSystemMetrics(0)
        self.screen_height = user32.GetSystemMetrics(1)
        self._left_is_down = False
        self._right_is_down = False

    def update_screen_size(self):
        self.screen_width = user32.GetSystemMetrics(0)
        self.screen_height = user32.GetSystemMetrics(1)

    def move_to(self, x, y):
        """Clamp coordinates to screen bounds and move pointer instantly."""
        target_x = max(0, min(self.screen_width - 1, int(x)))
        target_y = max(0, min(self.screen_height - 1, int(y)))
        user32.SetCursorPos(target_x, target_y)

    def left_down(self):
        if not self._left_is_down:
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            self._left_is_down = True

    def left_up(self):
        if self._left_is_down:
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self._left_is_down = False

    def click(self):
        self.left_down()
        time.sleep(0.015)
        self.left_up()

    def double_click(self):
        self.click()
        time.sleep(0.08)
        self.click()

    def right_click(self):
        user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        time.sleep(0.015)
        user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)

    def scroll(self, steps):
        """Scroll vertical: positive steps scroll up, negative scroll down."""
        delta = int(steps * WHEEL_DELTA)
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)

    @property
    def is_dragging(self):
        return self._left_is_down

    def release_all(self):
        """Ensure all buttons are released cleanly."""
        if self._left_is_down:
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self._left_is_down = False
        if self._right_is_down:
            user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            self._right_is_down = False
