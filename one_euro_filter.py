import math
import time

class LowPassFilter:
    def __init__(self, alpha=0.5):
        self.__set_alpha(alpha)
        self.__y = None
        self.__s = None

    def __set_alpha(self, alpha):
        if alpha <= 0 or alpha > 1.0:
            alpha = max(0.0001, min(1.0, alpha))
        self.__alpha = alpha

    def filter(self, value, alpha=None):
        if alpha is not None:
            self.__set_alpha(alpha)
        if self.__s is None:
            s = value
        else:
            s = self.__alpha * value + (1.0 - self.__alpha) * self.__s
        self.__y = value
        self.__s = s
        return s

    def last_value(self):
        return self.__y


class OneEuroFilter:
    """
    1-Euro Filter: Adaptive low-pass filter specifically designed by Gery Casiez et al.
    for noisy real-time human tracking.
    Eliminates jitter when hand is steady or moving slowly,
    while eliminating lag when hand is moving quickly.
    """
    def __init__(self, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()
        self.last_time = None

    def _alpha(self, cutoff, dt):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, x, timestamp=None):
        if timestamp is None:
            timestamp = time.time()

        if self.last_time is None:
            self.last_time = timestamp
            self.x_filter.filter(x)
            return x

        dt = timestamp - self.last_time
        if dt <= 1e-5:
            dt = 1e-4
        self.last_time = timestamp

        prev_x = self.x_filter.last_value()
        if prev_x is None:
            prev_x = x
        dx = (x - prev_x) / dt

        # Filter the derivative
        edx = self.dx_filter.filter(dx, alpha=self._alpha(self.d_cutoff, dt))
        # Compute dynamic cutoff frequency based on velocity
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self.x_filter.filter(x, alpha=self._alpha(cutoff, dt))

    def reset(self):
        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()
        self.last_time = None


class PointFilter:
    """
    2D coordinate filter wrapping two 1-Euro filters for smooth (X, Y) cursor tracking.
    """
    def __init__(self, min_cutoff=1.0, beta=0.05, d_cutoff=1.0):
        self.filter_x = OneEuroFilter(min_cutoff, beta, d_cutoff)
        self.filter_y = OneEuroFilter(min_cutoff, beta, d_cutoff)

    def filter(self, x, y, timestamp=None):
        fx = self.filter_x.filter(x, timestamp)
        fy = self.filter_y.filter(y, timestamp)
        return fx, fy

    def reset(self):
        self.filter_x.reset()
        self.filter_y.reset()
