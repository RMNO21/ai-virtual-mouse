import math
import time

class SmoothFilter:
    """
    Ultra-High Precision Dual-Stage Filter.
    Features:
    - Micro-Tremor Deadzone: Completely ignores sensor noise (< deadzone px).
    - Precision Micro-Aiming Zone: Allows effortless 1-pixel adjustments for clicking tiny buttons/text.
    - Non-linear Ballistics: Accelerates smoothly for long cross-screen movements with zero latency.
    """
    def __init__(self, deadzone=1.8, min_alpha=0.09, max_alpha=0.88, precision_range=30.0, speed_range=140.0):
        self.deadzone = float(deadzone)
        self.min_alpha = float(min_alpha)
        self.max_alpha = float(max_alpha)
        self.precision_range = float(precision_range)
        self.speed_range = float(speed_range)
        self.curr_x = None
        self.curr_y = None
        self.last_time = None

    def filter(self, target_x, target_y, timestamp=None):
        if timestamp is None:
            timestamp = time.time()

        if self.curr_x is None or self.curr_y is None:
            self.curr_x = float(target_x)
            self.curr_y = float(target_y)
            self.last_time = timestamp
            return self.curr_x, self.curr_y

        dx = target_x - self.curr_x
        dy = target_y - self.curr_y
        dist = math.hypot(dx, dy)

        # 1. Micro-tremor deadzone: zero jitter when holding hand still
        if dist <= self.deadzone:
            return self.curr_x, self.curr_y

        eff_dist = dist - self.deadzone

        # 2. Multi-tier precision ballistics
        if eff_dist <= self.precision_range:
            # Precision mode: smooth micro-aiming for tiny icons, links, and text
            t = eff_dist / self.precision_range
            alpha = self.min_alpha + (0.28 - self.min_alpha) * (t ** 1.6)
        else:
            # Glide & flick mode: fast responsive tracking across screen
            span = max(1.0, self.speed_range - self.precision_range)
            t = min(1.0, (eff_dist - self.precision_range) / span)
            alpha = 0.28 + (self.max_alpha - 0.28) * (t ** 1.2)

        self.curr_x += dx * alpha
        self.curr_y += dy * alpha
        self.last_time = timestamp
        return self.curr_x, self.curr_y

    def reset(self):
        self.curr_x = None
        self.curr_y = None
        self.last_time = None
