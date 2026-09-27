import math
import time

class GestureDetector:
    """
    Ergonomic Hand Gesture Detector with Open-Hand Verification:
    - Cursor Movement: Driven by the Middle finger / Hand (lm[12] / lm[9]).
    - Click Trigger:
      * REQUIREMENT 1: The hand MUST be OPEN (Middle and Ring fingers extended).
      * REQUIREMENT 2: ONLY the Index finger bends down / curls to click.
      If the rest of the hand is closed or made into a fist, clicks are strictly prevented!
    - Drag & Drop: Holding only the index finger bent while hand remains open.
    - Right Click: Thumb + Middle pinch while hand is open.
    - Scroll: Middle + Ring fingers moved up/down.
    """

    def __init__(self,
                 pinch_threshold=0.38,
                 release_threshold=0.52,
                 drag_hold_delay=0.22,
                 double_click_window=0.35,
                 **kwargs):
        self.pinch_threshold = pinch_threshold
        self.release_threshold = release_threshold
        self.drag_hold_delay = drag_hold_delay
        self.double_click_window = double_click_window

        # Index click state
        self.index_is_down = False
        self.index_down_start_time = 0.0
        self.is_dragging = False
        self.last_click_time = 0.0

        # Right click state
        self.right_is_down = False
        self.right_down_start_time = 0.0

        # Scroll state
        self.last_scroll_y = None

        # Hand open state
        self.hand_is_open = False
        self.last_cursor_pos = (0.5, 0.5)

    @staticmethod
    def _dist(p1, p2):
        return math.hypot(p1.x - p2.x, p1.y - p2.y)

    def process(self, landmarks, frame_w, frame_h):
        """
        Process MediaPipe landmarks with strict open-hand check.
        """
        now = time.time()
        lm = landmarks.landmark
        wrist = lm[0]

        # Reference scale: Wrist (0) to Middle Knuckle (9)
        ref_dist = self._dist(wrist, lm[9])
        if ref_dist < 1e-4:
            ref_dist = 0.1

        # -----------------------------------------------------------------
        # 1. CHECK EXTENSION OF OTHER FINGERS (Is the hand open?)
        # -----------------------------------------------------------------
        # Middle finger extension: Tip (12) vs Knuckle (9)
        m_ext = self._dist(lm[12], wrist) / max(1e-4, self._dist(lm[9], wrist))
        middle_open = (m_ext > 1.35) and (lm[12].y < lm[10].y)

        # Ring finger extension: Tip (16) vs Knuckle (13)
        r_ext = self._dist(lm[16], wrist) / max(1e-4, self._dist(lm[13], wrist))
        ring_open = (r_ext > 1.25) and (lm[16].y < lm[14].y)

        # Pinky extension: Tip (20) vs Knuckle (17)
        p_ext = self._dist(lm[20], wrist) / max(1e-4, self._dist(lm[17], wrist))
        pinky_open = (p_ext > 1.20) and (lm[20].y < lm[18].y)

        # Hand is considered OPEN if middle finger AND at least one other finger (ring or pinky) are extended
        self.hand_is_open = middle_open and (ring_open or pinky_open)

        # -----------------------------------------------------------------
        # 2. CURSOR POSITION: Rigid Palm Knuckle + Middle finger blend
        # -----------------------------------------------------------------
        cursor_x = lm[9].x * 0.65 + lm[12].x * 0.35
        cursor_y = lm[9].y * 0.65 + lm[12].y * 0.35
        self.last_cursor_pos = (cursor_x, cursor_y)

        # -----------------------------------------------------------------
        # 3. CHECK INDEX FINGER STATE (Only bends to click)
        # -----------------------------------------------------------------
        idx_ext = self._dist(lm[8], wrist) / max(1e-4, self._dist(lm[5], wrist))
        d_thumb_index = self._dist(lm[4], lm[8]) / ref_dist

        # Index is bent if tip drops below PIP or distance from wrist collapses or pinches thumb
        index_bent = (lm[8].y > lm[6].y) or (idx_ext < 1.35) or (d_thumb_index < 0.36)

        action = {
            'state': 'MOVE',
            'cursor_pos': self.last_cursor_pos,
            'scroll_amount': 0.0,
            'is_dragging': self.is_dragging,
            'hand_is_open': self.hand_is_open
        }

        # If the hand is NOT open (e.g. fist, closed hand, relaxed hand):
        # We STRICTLY DO NOT CLICK! Cancel any ongoing click/drag.
        if not self.hand_is_open:
            if self.is_dragging:
                self.is_dragging = False
                action['state'] = 'DRAG_END'
            self.index_is_down = False
            self.right_is_down = False
            self.last_scroll_y = None
            action['state'] = 'HAND_CLOSED'
            return action

        # -----------------------------------------------------------------
        # 4. SCROLL MODE: Middle + Ring up, Pinky down, Index NOT bent
        # -----------------------------------------------------------------
        if middle_open and ring_open and not pinky_open and not index_bent:
            mid_y = (lm[12].y + lm[16].y) / 2.0
            if self.last_scroll_y is not None:
                dy = (mid_y - self.last_scroll_y)
                if abs(dy) > 0.008:
                    action['state'] = 'SCROLL'
                    action['scroll_amount'] = -dy * 30.0
            self.last_scroll_y = mid_y

            if self.is_dragging:
                self.is_dragging = False
                action['state'] = 'DRAG_END'
            self.index_is_down = False
            return action
        else:
            self.last_scroll_y = None

        # -----------------------------------------------------------------
        # 5. RIGHT CLICK: Thumb + Middle pinch while hand is open
        # -----------------------------------------------------------------
        d_thumb_middle = self._dist(lm[4], lm[12]) / ref_dist
        if d_thumb_middle < 0.35 and not index_bent:
            if not self.right_is_down:
                self.right_is_down = True
                self.right_down_start_time = now
        else:
            if self.right_is_down:
                duration = now - self.right_down_start_time
                self.right_is_down = False
                if duration < 0.35:
                    action['state'] = 'RIGHT_CLICK'
                    return action

        # -----------------------------------------------------------------
        # 6. LEFT CLICK & DRAG: Hand IS OPEN and ONLY Index finger is bent!
        # -----------------------------------------------------------------
        if index_bent:
            if not self.index_is_down:
                # Index finger bent down while hand is open
                self.index_is_down = True
                self.index_down_start_time = now
            else:
                hold_duration = now - self.index_down_start_time
                if hold_duration >= self.drag_hold_delay:
                    if not self.is_dragging:
                        self.is_dragging = True
                        action['state'] = 'DRAG_START'
                    else:
                        action['state'] = 'DRAGGING'
        else:
            if self.index_is_down:
                # Index finger unbent/released back up while hand was open
                hold_duration = now - self.index_down_start_time
                self.index_is_down = False

                if self.is_dragging:
                    self.is_dragging = False
                    action['state'] = 'DRAG_END'
                elif hold_duration < self.drag_hold_delay:
                    # Quick tap of index finger -> Click!
                    if (now - self.last_click_time) < self.double_click_window:
                        action['state'] = 'DOUBLE_CLICK'
                    else:
                        action['state'] = 'CLICK'
                    self.last_click_time = now

        action['is_dragging'] = self.is_dragging
        return action

    def reset(self):
        self.index_is_down = False
        self.is_dragging = False
        self.right_is_down = False
        self.last_scroll_y = None
        self.hand_is_open = False
