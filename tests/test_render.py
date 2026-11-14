# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
import numpy as np
from PIL import Image

from spherex.render import BACKGROUND, compose, difference_frames, display_limits, gif_bytes, to_diverging, to_gray


def test_gray_handles_nan_and_range():
    data = np.array([[0.0, 5.0, 10.0, np.nan]])
    out = to_gray(data, 0.0, 10.0)
    assert out[0, 0] == 0 and out[0, 2] == 255 and out[0, 3] == BACKGROUND


def test_shared_limits_cover_all_frames():
    low, high = display_limits([np.zeros((5, 5)), np.full((5, 5), 10.0)], 0, 100)
    assert (low, high) == (0.0, 10.0)


def test_difference_is_zero_for_first_frame():
    a, b = np.ones((3, 3)), np.full((3, 3), 4.0)
    diffs = difference_frames([a, b])
    assert np.all(diffs[0] == 0) and np.all(diffs[1] == 3)
    assert to_diverging(diffs[0], 1.0)[0, 0] == 127


def test_compose_flips_rows_so_north_is_up():
    gray = np.zeros((4, 4), dtype=np.uint8)
    gray[3, 0] = 255  # top row in FITS order (north)
    image = compose(gray, "label", scale=1)
    assert image.getpixel((0, 0)) == (255, 255, 255)


def test_gif_has_all_frames():
    frames = [Image.new("RGB", (8, 8), (i * 40, 0, 0)) for i in range(3)]
    data = gif_bytes(frames, 100)
    assert data[:3] == b"GIF"
    assert Image.open(__import__("io").BytesIO(data)).n_frames == 3


def test_fill_small_holes_fills_star_core_but_not_empty_border():
    from spherex.render import fill_small_holes

    data = np.zeros((9, 9))
    data[4, 4] = np.nan  # saturated core
    data[3, 4] = 50.0
    data[:, 0] = np.nan  # strip outside the data
    data[:, 1] = np.nan
    data[:, 2] = np.nan
    data[:, 3] = np.nan
    filled = fill_small_holes(data, passes=1)
    assert filled[4, 4] == 50.0
    assert np.isnan(filled[4, 0])
