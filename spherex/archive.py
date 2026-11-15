# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Find SPHEREx spectral images that cover a sky position and download cutouts of them from IRSA."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import requests
from astropy import log as astropy_log
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning

IRSA = "https://irsa.ipac.caltech.edu/"
TAP_URL = IRSA + "TAP/sync"
USER_AGENT = "nejma/1.0 (NASA Space Apps 2026)"

# Wavelength range of each SPHEREx detector in micrometres, measured from the archive's plane table.
DETECTORS = {
    1: (0.75, 1.12),
    2: (1.10, 1.65),
    3: (1.63, 2.43),
    4: (2.40, 3.85),
    5: (3.81, 4.43),
    6: (4.41, 5.01),
}

RETRY_STATUS = {429, 500, 502, 503, 504}
QUERY_MAX_AGE_S = 12 * 3600

# SPHEREx headers carry SIP terms without the "-SIP" suffix; astropy applies them and logs a notice we do not need.
astropy_log.setLevel("WARNING")
warnings.simplefilter("ignore", FITSFixedWarning)

_local = threading.local()


def _session() -> requests.Session:
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
        _local.session.headers["User-Agent"] = USER_AGENT
    return _local.session


def cache_dir() -> Path:
    """Directory for downloaded cutouts and query results (outside the repository)."""
    if os.environ.get("DOKDO_GULL_CACHE"):
        base = Path(os.environ["DOKDO_GULL_CACHE"])
    elif os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"]) / "dokdo-gull" / "cache"
    else:
        base = Path.home() / ".cache" / "dokdo-gull"
    base.mkdir(parents=True, exist_ok=True)
    return base


def http_get(url: str, *, params: dict | None = None, timeout: float = 120, attempts: int = 4) -> requests.Response:
    """GET with retries on timeouts and on the HTTP errors IRSA returns when it is busy."""
    delay = 2.0
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = _session().get(url, params=params, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            error = exc
        else:
            if response.status_code == 200:
                return response
            if response.status_code not in RETRY_STATUS:
                response.raise_for_status()
            error = requests.HTTPError(f"HTTP {response.status_code} from {url}", response=response)
        if attempt < attempts - 1:
            time.sleep(delay)
            delay *= 2
    assert error is not None
    raise error


@dataclass(frozen=True)
class ImageRecord:
    """One SPHEREx spectral image that covers the requested position."""

    uri: str
    detector: int
    mjd: float


def query_images(ra: float, dec: float, detector: int | None = None, *, timeout: float = 300, attempts: int = 4) -> list[ImageRecord]:
    """List every spectral image covering (ra, dec), oldest first.

    No data release is named, so images from new releases show up automatically.
    Results are cached on disk for a few hours.
    """
    key = f"{ra:.4f}_{dec:+.4f}_{detector or 'all'}"
    path = cache_dir() / "queries" / f"{key}.json"
    if path.exists() and time.time() - path.stat().st_mtime < QUERY_MAX_AGE_S:
        return [ImageRecord(**row) for row in json.loads(path.read_text())]

    band = f"AND p.energy_bandpassname = 'SPHEREx-D{detector}' " if detector else ""
    adql = (
        "SELECT a.uri, p.energy_bandpassname, p.time_bounds_lower "
        "FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid "
        f"WHERE 1 = CONTAINS(POINT('ICRS', {ra:.6f}, {dec:.6f}), p.poly) {band}"
        "ORDER BY p.time_bounds_lower"
    )
    response = http_get(TAP_URL, params={"QUERY": adql, "FORMAT": "CSV"}, timeout=timeout, attempts=attempts)
    rows = list(csv.DictReader(io.StringIO(response.text)))
    records = [
        ImageRecord(
            uri=row["uri"],
            detector=int(row["energy_bandpassname"].rsplit("D", 1)[1]),
            mjd=float(row["time_bounds_lower"]),
        )
        for row in rows
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([r.__dict__ for r in records]))
    return records


@dataclass
class Cutout:
    """The parts of a SPHEREx spectral image cutout that the viewer uses."""

    uri: str
    detector: int
    mjd: float
    image: np.ndarray  # surface brightness, MJy/sr, zodiacal light not removed
    zodi: np.ndarray  # modelled zodiacal light, MJy/sr
    variance: np.ndarray  # (MJy/sr)^2
    flags: np.ndarray  # per-pixel bitmask
    header: fits.Header  # IMAGE header; holds the celestial WCS
    flag_bits: dict[str, int]  # flag name -> bit value, read from the FLAGS header
    wavelength_um: float  # central wavelength at the requested position
    bandwidth_um: float

    @property
    def wcs(self) -> WCS:
        return WCS(self.header)


def cutout_url(uri: str, ra: float, dec: float, size_deg: float) -> str:
    return f"{IRSA}{uri.lstrip('/')}?center={ra:.6f},{dec:.6f}d&size={size_deg:.4f}"


def _cache_path(uri: str, ra: float, dec: float, size_deg: float) -> Path:
    digest = hashlib.sha1(f"{uri}|{ra:.5f}|{dec:.5f}|{size_deg:.4f}".encode()).hexdigest()[:20]
    return cache_dir() / "cutouts" / f"{digest}.npz"


def _flag_bits(header: fits.Header) -> dict[str, int]:
    bits = {}
    for key in header:
        if key.startswith("MSKN"):
            mask_key = "MSKM" + key[4:]
            if mask_key in header:
                bits[str(header[key])] = int(header[mask_key])
    return bits


def _parse_cutout(content: bytes, record: ImageRecord, ra: float, dec: float) -> Cutout:
    with fits.open(io.BytesIO(content)) as hdul:
        header = hdul["IMAGE"].header.copy()
        image = hdul["IMAGE"].data.astype(np.float32)
        zodi = hdul["ZODI"].data.astype(np.float32)
        variance = hdul["VARIANCE"].data.astype(np.float32)
        flags = hdul["FLAGS"].data.astype(np.int32)
        flag_bits = _flag_bits(hdul["FLAGS"].header)
        x, y = WCS(header).world_to_pixel(SkyCoord(ra, dec, unit="deg"))
        spectral = WCS(header, fobj=hdul, key="W")
        spectral.sip = None
        wavelength, bandwidth = spectral.pixel_to_world_values(float(x), float(y))
    return Cutout(
        uri=record.uri,
        detector=record.detector,
        mjd=float(header.get("MJD-AVG", record.mjd)),
        image=image,
        zodi=zodi,
        variance=variance,
        flags=flags,
        header=header,
        flag_bits=flag_bits,
        wavelength_um=float(wavelength),
        bandwidth_um=float(bandwidth),
    )


def _save(path: Path, cutout: Cutout) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(
        tmp,
        image=cutout.image,
        zodi=cutout.zodi,
        variance=cutout.variance,
        flags=cutout.flags,
        meta=np.array(
            json.dumps(
                {
                    "uri": cutout.uri,
                    "detector": cutout.detector,
                    "mjd": cutout.mjd,
                    "header": cutout.header.tostring(),
                    "flag_bits": cutout.flag_bits,
                    "wavelength_um": cutout.wavelength_um,
                    "bandwidth_um": cutout.bandwidth_um,
                }
            )
        ),
    )
    os.replace(tmp, path)


def _load(path: Path) -> Cutout:
    with np.load(path) as data:
        meta = json.loads(str(data["meta"]))
        return Cutout(
            uri=meta["uri"],
            detector=meta["detector"],
            mjd=meta["mjd"],
            image=data["image"],
            zodi=data["zodi"],
            variance=data["variance"],
            flags=data["flags"],
            header=fits.Header.fromstring(meta["header"]),
            flag_bits=meta["flag_bits"],
            wavelength_um=meta["wavelength_um"],
            bandwidth_um=meta["bandwidth_um"],
        )


def get_cutout(record: ImageRecord, ra: float, dec: float, size_deg: float) -> Cutout:
    """Return a cutout centred on (ra, dec), from the disk cache when possible."""
    path = _cache_path(record.uri, ra, dec, size_deg)
    if path.exists():
        return _load(path)
    response = http_get(cutout_url(record.uri, ra, dec, size_deg), timeout=180)
    if not response.content.startswith(b"SIMPLE"):
        raise ValueError(f"IRSA did not return a FITS file for {record.uri}")
    cutout = _parse_cutout(response.content, record, ra, dec)
    _save(path, cutout)
    return cutout


def is_cached(record: ImageRecord, ra: float, dec: float, size_deg: float) -> bool:
    return _cache_path(record.uri, ra, dec, size_deg).exists()


def get_cutouts(
    records: list[ImageRecord],
    ra: float,
    dec: float,
    size_deg: float,
    *,
    workers: int = 6,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[list[Cutout], list[tuple[ImageRecord, str]]]:
    """Download cutouts in parallel. Returns the cutouts (oldest first) and the records that failed."""
    cutouts: list[Cutout] = []
    failures: list[tuple[ImageRecord, str]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(get_cutout, r, ra, dec, size_deg): r for r in records}
        for future in as_completed(futures):
            record = futures[future]
            try:
                cutouts.append(future.result())
            except Exception as exc:  # one bad image should not stop the others
                failures.append((record, f"{type(exc).__name__}: {exc}"))
            done += 1
            if progress:
                progress(done, len(records))
    cutouts.sort(key=lambda c: c.mjd)
    return cutouts, failures
