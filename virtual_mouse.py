import os
import sys

# Suppress verbose C++ logging from TensorFlow / MediaPipe
os.environ["GLOG_minloglevel"] = "2"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import cv2
import json
import time
import threading
import keyboard
import mediapipe as mp
import numpy as np

from smooth_filter import SmoothFilter
from mouse_controller import MouseController
from gesture_detector import GestureDetector
from sound_feedback import SoundFeedback

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config():
    default_config = {
        "hotkeys": {"toggle": "ctrl+alt+m", "toggle_alternative": "f8", "exit": "ctrl+alt+q"},
        "camera": {"device_id": 0, "width": 640, "height": 480, "fps": 60},
        "interaction": {
            "margin_left": 0.15, "margin_right": 0.15,
            "margin_top": 0.15, "margin_bottom": 0.20,
            "speed_multiplier": 1.15,
            "pinch_threshold": 0.38, "release_threshold": 0.52,
            "drag_hold_delay": 0.22, "scroll_sensitivity": 30.0
        },
        "filter": {
            "deadzone": 1.8, "min_alpha": 0.09, "max_alpha": 0.88,
            "precision_range": 30.0, "speed_range": 140.0
        },
        "ui": {
            "sound_effects": True, "show_preview": True,
            "preview_width": 380, "preview_height": 285,
            "window_name": "AI Virtual Mouse (Preview)"
        }
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                return cfg
        except Exception as e:
            print(f"[Warning] Failed to load config.json: {e}, using defaults.")
    return default_config


class VirtualMouseApp:
    def __init__(self):
        self.cfg = load_config()
        self.is_active = False
        self.should_exit = False
        self._lock = threading.Lock()

        # Controllers & Modules
        self.mouse = MouseController()
        self.sound = SoundFeedback(enabled=self.cfg["ui"].get("sound_effects", True))
        
        filter_cfg = self.cfg.get("filter", {})
        self.filter = SmoothFilter(
            deadzone=filter_cfg.get("deadzone", 1.8),
            min_alpha=filter_cfg.get("min_alpha", 0.09),
            max_alpha=filter_cfg.get("max_alpha", 0.88),
            precision_range=filter_cfg.get("precision_range", 30.0),
            speed_range=filter_cfg.get("speed_range", 140.0)
        )

        inter_cfg = self.cfg.get("interaction", {})
        self.detector = GestureDetector(
            pinch_threshold=inter_cfg.get("pinch_threshold", 0.38),
            release_threshold=inter_cfg.get("release_threshold", 0.52),
            drag_hold_delay=inter_cfg.get("drag_hold_delay", 0.22)
        )

        # UI & Filter State
        self.show_preview = self.cfg["ui"].get("show_preview", True)
        self.fps = 0.0
        self.smooth_norm_x = None
        self.smooth_norm_y = None

        # MediaPipe initialization
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_draw_styles = mp.solutions.drawing_styles

        self.last_toggle_time = 0.0
        self.worker_thread = None

    def toggle(self):
        """Toggle active camera tracking ON/OFF with robust debounce against key-repeat."""
        now = time.time()
        with self._lock:
            if now - self.last_toggle_time < 0.8:
                return
            self.last_toggle_time = now

            if self.is_active:
                self.is_active = False
                print("\n[AI Virtual Mouse] >> DEACTIVATED (Camera Released, Standby Mode)")
                self.mouse.release_all()
                self.sound.deactivated()
            else:
                self.is_active = True
                print("\n[AI Virtual Mouse] >> ACTIVATED (Camera Tracking Started)")
                self.sound.activated()
                if self.worker_thread is None or not self.worker_thread.is_alive():
                    self.worker_thread = threading.Thread(target=self._tracking_loop, daemon=True)
                    self.worker_thread.start()

    def exit_app(self):
        print("\n[AI Virtual Mouse] >> Shutting down...")
        self.is_active = False
        self.should_exit = True
        self.mouse.release_all()

    def _open_camera(self):
        cam_id = self.cfg["camera"].get("device_id", 0)
        # Use DirectShow (CAP_DSHOW) on Windows for near-instant camera startup and low latency
        cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(cam_id)
        
        w = self.cfg["camera"].get("width", 640)
        h = self.cfg["camera"].get("height", 480)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Eliminate frame queue lag
        return cap

    def _tracking_loop(self):
        """High-performance tracking loop when active."""
        cap = None
        hands = None

        try:
            while not self.should_exit:
                if not self.is_active:
                    # Inactive: Ensure camera and windows are released cleanly
                    if cap is not None and cap.isOpened():
                        cap.release()
                        cap = None
                    if hands is not None:
                        hands.close()
                        hands = None
                    cv2.destroyAllWindows()
                    self.filter.reset()
                    self.detector.reset()
                    self.smooth_norm_x = None
                    self.smooth_norm_y = None
                    time.sleep(0.05)
                    continue

                # Just activated: open camera and initialize MediaPipe
                if cap is None or not cap.isOpened():
                    cap = self._open_camera()
                    if not cap.isOpened():
                        print("[Error] Could not open webcam! Please check camera permissions or index.")
                        self.is_active = False
                        time.sleep(1.0)
                        continue

                if hands is None:
                    hands = self.mp_hands.Hands(
                        static_image_mode=False,
                        max_num_hands=1,
                        model_complexity=1, # High-precision 3D hand regression model
                        min_detection_confidence=0.75,
                        min_tracking_confidence=0.75
                    )

                prev_time = time.time()
                inter_cfg = self.cfg.get("interaction", {})
                margin_left = inter_cfg.get("margin_left", inter_cfg.get("margin_x", 0.15))
                margin_right = inter_cfg.get("margin_right", inter_cfg.get("margin_x", 0.15))
                margin_top = inter_cfg.get("margin_top", inter_cfg.get("margin_y", 0.15))
                margin_bottom = inter_cfg.get("margin_bottom", 0.20)
                speed_mult = inter_cfg.get("speed_multiplier", 1.15)
                scroll_sens = inter_cfg.get("scroll_sensitivity", 30.0)

                while self.is_active and not self.should_exit:
                    ret, frame = cap.read()
                    if not ret:
                        time.sleep(0.01)
                        continue

                    now = time.time()
                    dt = now - prev_time
                    prev_time = now
                    if dt > 0:
                        self.fps = 0.9 * self.fps + 0.1 * (1.0 / dt)

                    # Mirror image for natural hand movement
                    frame = cv2.flip(frame, 1)
                    fh, fw = frame.shape[:2]

                    # Convert to RGB for MediaPipe
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = hands.process(rgb)

                    action_str = "STANDBY"

                    if results.multi_hand_landmarks:
                        landmarks = results.multi_hand_landmarks[0]
                        action = self.detector.process(landmarks, fw, fh)
                        state = action['state']
                        norm_x, norm_y = action['cursor_pos']

                        # Sub-pixel temporal pre-filtering for surgical precision
                        if self.smooth_norm_x is None:
                            self.smooth_norm_x = norm_x
                            self.smooth_norm_y = norm_y
                        else:
                            self.smooth_norm_x = self.smooth_norm_x * 0.70 + norm_x * 0.30
                            self.smooth_norm_y = self.smooth_norm_y * 0.70 + norm_y * 0.30

                        use_x = self.smooth_norm_x if state == 'MOVE' else norm_x
                        use_y = self.smooth_norm_y if state == 'MOVE' else norm_y

                        # Coordinate mapping with active margins
                        span_x = 1.0 - margin_left - margin_right
                        span_y = 1.0 - margin_top - margin_bottom

                        if span_x > 0.01:
                            clamped_x = (use_x - margin_left) / span_x
                        else:
                            clamped_x = use_x

                        if span_y > 0.01:
                            clamped_y = (use_y - margin_top) / span_y
                        else:
                            clamped_y = use_y

                        if speed_mult != 1.0:
                            clamped_x = (clamped_x - 0.5) * speed_mult + 0.5
                            clamped_y = (clamped_y - 0.5) * speed_mult + 0.5

                        clamped_x = max(0.0, min(1.0, clamped_x))
                        clamped_y = max(0.0, min(1.0, clamped_y))

                        raw_target_x = clamped_x * self.mouse.screen_width
                        raw_target_y = clamped_y * self.mouse.screen_height

                        # Filter coordinates with deadzone + velocity-adaptive lerp
                        filtered_x, filtered_y = self.filter.filter(raw_target_x, raw_target_y, timestamp=now)

                        # Handle States
                        if state in ('MOVE', 'DRAGGING', 'DRAG_START'):
                            self.mouse.move_to(filtered_x, filtered_y)

                        if state == 'CLICK':
                            self.mouse.move_to(filtered_x, filtered_y)
                            self.mouse.click()
                            self.sound.click()
                            action_str = "CLICK"
                        elif state == 'DOUBLE_CLICK':
                            self.mouse.move_to(filtered_x, filtered_y)
                            self.mouse.double_click()
                            self.sound.double_click()
                            action_str = "DOUBLE CLICK"
                        elif state == 'DRAG_START':
                            self.mouse.left_down()
                            self.sound.drag_start()
                            action_str = "DRAGGING (HOLD)"
                        elif state == 'DRAGGING':
                            action_str = "DRAGGING (HOLD)"
                        elif state == 'DRAG_END':
                            self.mouse.left_up()
                            self.sound.drag_end()
                            action_str = "RELEASE"
                        elif state == 'RIGHT_CLICK':
                            self.mouse.right_click()
                            self.sound.right_click()
                            action_str = "RIGHT CLICK"
                        elif state == 'SCROLL':
                            scroll_amount = action['scroll_amount'] * (scroll_sens / 30.0)
                            self.mouse.scroll(scroll_amount)
                            action_str = "SCROLLING"
                        elif state == 'MOVE':
                            if self.detector.index_is_down:
                                action_str = "INDEX CLICKING"
                            else:
                                action_str = "TRACKING"
                        elif state == 'HAND_CLOSED':
                            action_str = "HAND CLOSED (RESTING)"

                        # Draw landmarks and visual indicators if preview enabled
                        if self.show_preview:
                            self._draw_overlay(frame, landmarks, fw, fh, margin_left, margin_right, margin_top, margin_bottom, action_str, norm_x, norm_y)
                    else:
                        # Hand not in frame
                        if self.detector.is_dragging:
                            self.mouse.left_up()
                            self.detector.reset()
                        self.filter.reset()
                        action_str = "SEARCHING FOR HAND"

                        if self.show_preview:
                            self._draw_overlay(frame, None, fw, fh, margin_left, margin_right, margin_top, margin_bottom, action_str, 0, 0)

                    # Show Preview HUD
                    if self.show_preview:
                        pw = self.cfg["ui"].get("preview_width", 380)
                        ph = self.cfg["ui"].get("preview_height", 285)
                        disp_frame = cv2.resize(frame, (pw, ph))
                        cv2.imshow(self.cfg["ui"].get("window_name", "AI Virtual Mouse (Preview)"), disp_frame)

                        key = cv2.waitKey(1) & 0xFF
                        if key == 27 or key == ord('q'):
                            self.toggle()
                        elif key == ord('h') or key == ord('H'):
                            self.show_preview = False
                            cv2.destroyAllWindows()
                            print("[Info] Camera preview hidden. Press toggle shortcut anytime to deactivate.")
                        elif key == ord('s') or key == ord('S'):
                            self.sound.enabled = not self.sound.enabled
                            print(f"[Info] Sound effects: {'Enabled' if self.sound.enabled else 'Disabled'}")

        except Exception as e:
            print(f"[Error in tracking loop] {e}")
        finally:
            if cap is not None and cap.isOpened():
                cap.release()
            if hands is not None:
                hands.close()
            cv2.destroyAllWindows()
            self.mouse.release_all()

    def _draw_overlay(self, frame, landmarks, fw, fh, margin_left, margin_right, margin_top, margin_bottom, action_str, norm_x, norm_y):
        """Render stylish, non-intrusive HUD on camera preview."""
        # 1. Active Margin Box (comfort boundary for full-screen cursor mapping)
        if margin_left > 0.005 or margin_top > 0.005 or margin_bottom > 0.005:
            bx1 = int(fw * margin_left)
            by1 = int(fh * margin_top)
            bx2 = int(fw * (1.0 - margin_right))
            by2 = int(fh * (1.0 - margin_bottom))
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (200, 200, 200), 1, cv2.LINE_AA)
            cv2.putText(frame, "ACTIVE ZONE", (bx1 + 5, by1 + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)

        # 2. Hand Landmarks
        if landmarks:
            self.mp_draw.draw_landmarks(
                frame,
                landmarks,
                self.mp_hands.HAND_CONNECTIONS,
                self.mp_draw_styles.get_default_hand_landmarks_style(),
                self.mp_draw_styles.get_default_hand_connections_style()
            )
            # Highlight cursor tracking point (Middle finger)
            cx, cy = int(norm_x * fw), int(norm_y * fh)
            cv2.circle(frame, (cx, cy), 9, (0, 255, 128), -1, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), 13, (0, 255, 128), 2, cv2.LINE_AA)

            # Highlight Index fingertip (Click button)
            lm_idx = landmarks.landmark[8]
            ix, iy = int(lm_idx.x * fw), int(lm_idx.y * fh)
            btn_color = (0, 70, 255) if self.detector.index_is_down else (0, 220, 255)
            cv2.circle(frame, (ix, iy), 7, btn_color, -1, cv2.LINE_AA)

        # 3. Status Header
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (fw, 55), (20, 24, 28), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        color_map = {
            "TRACKING": (100, 255, 100),
            "INDEX CLICKING": (0, 70, 255),
            "CLICK": (0, 255, 255),
            "DOUBLE CLICK": (0, 220, 255),
            "DRAGGING (HOLD)": (0, 70, 255),
            "RELEASE": (200, 200, 200),
            "RIGHT CLICK": (255, 100, 255),
            "SCROLLING": (255, 200, 50),
            "HAND CLOSED (RESTING)": (140, 140, 190),
            "SEARCHING FOR HAND": (150, 150, 150)
        }
        badge_color = color_map.get(action_str, (220, 220, 220))

        cv2.putText(frame, action_str, (12, 34), cv2.FONT_HERSHEY_DUPLEX, 0.8, badge_color, 2, cv2.LINE_AA)

        fps_text = f"{int(self.fps)} FPS"
        cv2.putText(frame, fps_text, (fw - 95, 34), cv2.FONT_HERSHEY_DUPLEX, 0.65, (180, 220, 180), 1, cv2.LINE_AA)

        # Bottom footer
        cv2.rectangle(overlay, (0, fh - 28), (fw, fh), (15, 15, 15), -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
        help_text = "Shortcut: Ctrl+Alt+M / F8 | H: Hide | Q: Stop"
        cv2.putText(frame, help_text, (10, fh - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)


def print_banner(cfg):
    toggle_key = cfg["hotkeys"].get("toggle", "ctrl+alt+m").upper()
    alt_key = cfg["hotkeys"].get("toggle_alternative", "f8").upper()
    exit_key = cfg["hotkeys"].get("exit", "ctrl+alt+q").upper()
    print("=" * 65)
    print("   AI VIRTUAL MOUSE (HIGH-PERFORMANCE ULTRA-SMOOTH)")
    print("=" * 65)
    print(f" [!] Toggle Shortcut (ON/OFF) : [{toggle_key}] or [{alt_key}]")
    print(f" [!] Exit Application Shortcut: [{exit_key}]")
    print("-" * 65)
    print(" Hand Gestures Guide:")
    print("   1. Move Cursor       : Move Middle Finger / Hand")
    print("   2. Left Click        : Hand OPEN, bend ONLY Index Finger down")
    print("   3. Drag & Hold       : Hand OPEN, hold Index Finger bent (>0.2s)")
    print("   4. Hand Closed / Fist: Clicks DISABLED (safe resting mode)")
    print("   5. Right Click       : Hand OPEN, pinch Thumb + Middle finger")
    print("   6. Scroll Page       : Middle + Ring fingers together, move up/down")
    print("-" * 65)
    print(" Key Features:")
    print("   * Open-Hand Safety: Only clicks when hand is open and index bends")
    print("   * Ultra-Smooth Filter: Deadzone + Velocity Adaptive Lerp")
    print("   * Zero Click Drift: Decoupled finger tracking")
    print("   * Zero CPU & RAM consumption in standby (camera fully released)")
    print("=" * 65)
    print("\nApplication is in Standby mode. Press the shortcut to activate...")


def main():
    app = VirtualMouseApp()
    cfg = app.cfg

    print_banner(cfg)

    # Register global hotkeys
    toggle_k1 = cfg["hotkeys"].get("toggle", "ctrl+alt+m")
    toggle_k2 = cfg["hotkeys"].get("toggle_alternative", "f8")
    exit_k = cfg["hotkeys"].get("exit", "ctrl+alt+q")

    try:
        keyboard.add_hotkey(toggle_k1, app.toggle)
        if toggle_k2:
            keyboard.add_hotkey(toggle_k2, app.toggle)
        keyboard.add_hotkey(exit_k, app.exit_app)
    except Exception as e:
        print(f"[Warning] Could not register global hotkeys directly: {e}")
        print("Tip: Run as Administrator if global hotkeys are blocked by Windows.")

    if cfg.get("start_active", False):
        app.toggle()

    try:
        while not app.should_exit:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        app.exit_app()
        time.sleep(0.3)
        print("\n[AI Virtual Mouse] Goodbye!")

if __name__ == "__main__":
    main()
