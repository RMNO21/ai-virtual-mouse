# 🖱️ AI Virtual Mouse (High-Performance Webcam Hand Tracker)

A fast, lightweight, and ultra-smooth AI virtual mouse for Windows using MediaPipe and OpenCV.

---

## 🎯 Ultra-High Precision Architecture

1. **MediaPipe Model Complexity 1 (Full 3D Model):**
   - Upgraded from the low-accuracy Lite model to the high-precision Full Hand Landmark model with 0.75 detection/tracking confidence thresholds.
2. **Sub-Pixel Landmark Pre-Filtering:**
   - Raw normalized coordinates from the camera are pre-filtered with an adaptive temporal low-pass filter at the camera level, eliminating sensor noise before screen scaling.
3. **Multi-Tier Precision Ballistics:**
   - **Deadzone (1.8px):** Eliminates 100% of camera sensor micro-jitter when hand is still.
   - **Precision Micro-Aiming Zone (<30px):** Sub-pixel power damping allowing 1-pixel micro-steps to target checkboxes, individual text characters, and small buttons with surgical control.
   - **Glide & Flick Zone (>30px):** Smooth acceleration to cross the entire screen with zero latency.
4. **Rigid Knuckle Anchor:**
   - Cursor guidance uses the anatomically rigid Palm Knuckle (`MIDDLE_FINGER_MCP`, index 9) combined with middle finger orientation, eliminating the tremor inherent to loose fingertips.
5. **Decoupled Open-Hand Clicking:**
   - Clicks are triggered purely by bending the Index finger while the hand is open, causing zero cursor drift.

---

## ⌨️ Global Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + Alt + M` or `F8` | Toggle tracking ON / OFF |
| `Ctrl + Alt + Q` | Exit application |
| `H` (inside preview window) | Hide preview window (run headless in background) |
| `S` (inside preview window) | Toggle sound effects ON / OFF |

---

## ✋ Hand Gestures Guide

| Gesture | Mouse Action | Notes |
|---|---|---|
| **Middle Finger / Hand movement** | **Move Cursor** | Precision aiming and smooth glide |
| **Hand OPEN + Tap Index Finger down** | **Left Click** | Quick tap down and up (like real mouse button) |
| **Hand OPEN + Double Tap Index Finger** | **Double Click** | Two quick taps |
| **Hand OPEN + Hold Index Finger down** | **Drag & Hold** | Hold index bent (>0.2s) to drag; lift to release |
| **Hand Closed / Fist** | **Resting (No Click)** | Clicks disabled when hand is not open |
| **Thumb + Middle finger pinch** | **Right Click** | Opens context menu |
| **Middle + Ring fingers together** | **Scroll** | Move hand up to scroll up, move down to scroll down |

---

## 🚀 How to Run

Double-click `run.bat` or run via command line:

```powershell
python virtual_mouse.py
```

Press **`F8`** or **`Ctrl + Alt + M`** to activate tracking. Press it again anytime to pause.
