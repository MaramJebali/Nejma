# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
import numpy as np

from spherex import showcase
from spherex.process import Frame, target_grid


def test_round_trip(tmp_path):
    wcs, shape = target_grid(10.0, 20.0, 0.05)
    frames = [
        Frame(detector=2, mjd_start=1.0, mjd_end=2.0, mjd_mid=1.5, n_images=3, n_available=5,
              data=np.full(shape, i, dtype=np.float32), wavelength_um=(1.1, 1.6), target_flags={"OVERFLOW": 3})
        for i in range(2)
    ]
    path = tmp_path / "x.npz"
    showcase.save(path, frames, wcs, {"built": "2026-11-14", "n_records": 7, "n_skipped": 0, "n_failures": 0})
    loaded, wcs2, info = showcase.load(path)
    assert len(loaded) == 2 and loaded[1].data[0, 0] == 1
    assert loaded[0].wavelength_um == (1.1, 1.6) and loaded[0].target_flags == {"OVERFLOW": 3}
    assert info["n_records"] == 7
    assert np.allclose(wcs2.world_to_pixel_values(10.0, 20.0), wcs.world_to_pixel_values(10.0, 20.0))


def test_saturation_mask_round_trip(tmp_path):
    wcs, shape = target_grid(10.0, 20.0, 0.05)
    mask = np.zeros(shape, dtype=bool)
    mask[3, 4] = True
    frame = Frame(detector=2, mjd_start=1.0, mjd_end=2.0, mjd_mid=1.5, n_images=3, n_available=5,
                  data=np.zeros(shape, dtype=np.float32), wavelength_um=(1.1, 1.6), saturated=mask)
    info = {"built": "2026-11-14", "n_records": 7, "n_skipped": 0, "n_failures": 0}
    showcase.save(tmp_path / "with.npz", [frame], wcs, info)
    loaded = showcase.load(tmp_path / "with.npz")[0][0]
    assert loaded.saturated[3, 4] and loaded.saturated.sum() == 1

    frame.saturated = None  # as in files saved before the mask existed
    showcase.save(tmp_path / "without.npz", [frame], wcs, info)
    assert showcase.load(tmp_path / "without.npz")[0][0].saturated is None


def test_path_is_stable():
    assert showcase.showcase_path("Barnard's Star", 0.1, 2).name == "barnard-s-star_fov0.1_d2.npz"
