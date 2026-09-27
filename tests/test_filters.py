import pytest
from one_euro_filter import OneEuroFilter
from smooth_filter import SmoothFilter

def test_one_euro_filter_initialization():
    f = OneEuroFilter(freq=60, mincutoff=1.0, beta=0.007, dcutoff=1.0)
    filtered = f(10.0, 0.0)
    assert filtered == 10.0

def test_smooth_filter_moving_average():
    sf = SmoothFilter(window_size=5)
    for v in [10, 20, 30]:
        sf.update(v)
    assert sf.get_average() == 20.0
