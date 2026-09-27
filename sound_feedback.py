import threading
import winsound

class SoundFeedback:
    def __init__(self, enabled=True):
        self.enabled = enabled

    def _play(self, freq, duration):
        if not self.enabled:
            return
        def _beep():
            try:
                winsound.Beep(freq, duration)
            except Exception:
                pass
        threading.Thread(target=_beep, daemon=True).start()

    def activated(self):
        if not self.enabled:
            return
        def _seq():
            try:
                winsound.Beep(1200, 70)
                winsound.Beep(1600, 90)
            except Exception:
                pass
        threading.Thread(target=_seq, daemon=True).start()

    def deactivated(self):
        if not self.enabled:
            return
        def _seq():
            try:
                winsound.Beep(1500, 70)
                winsound.Beep(1000, 90)
            except Exception:
                pass
        threading.Thread(target=_seq, daemon=True).start()

    def click(self):
        self._play(900, 30)

    def double_click(self):
        def _seq():
            try:
                winsound.Beep(900, 30)
                winsound.Beep(1100, 30)
            except Exception:
                pass
        threading.Thread(target=_seq, daemon=True).start()

    def right_click(self):
        self._play(1400, 45)

    def drag_start(self):
        self._play(750, 50)

    def drag_end(self):
        self._play(600, 40)
