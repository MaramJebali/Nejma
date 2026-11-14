# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
"""Turn what the user typed (coordinates or an object name) into a sky position."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import quote

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time

from .archive import http_get

SESAME_URL = "https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?"
CATALOG_EPOCH = 2000.0  # SIMBAD positions are given for epoch J2000
VIEW_EPOCH = 2026.0  # centre of the SPHEREx data so far

_SEXAGESIMAL = re.compile(r"[\d\s:+\-.hmsd°'\"]+")


@dataclass(frozen=True)
class Target:
    label: str
    ra: float  # degrees, at VIEW_EPOCH
    dec: float
    pm_ra_cosdec: float = 0.0  # mas/yr
    pm_dec: float = 0.0  # mas/yr
    source: str = "coordinates"

    def position_at(self, year: float) -> tuple[float, float]:
        """Position (degrees) at a decimal year, moving along the proper motion."""
        return propagate(self.ra, self.dec, self.pm_ra_cosdec, self.pm_dec, VIEW_EPOCH, year)

    @property
    def has_motion(self) -> bool:
        return bool(self.pm_ra_cosdec or self.pm_dec)


def propagate(ra: float, dec: float, pm_ra_cosdec: float, pm_dec: float, from_year: float, to_year: float) -> tuple[float, float]:
    """Linear proper-motion shift. Accurate to well under a pixel for the motions and time spans involved here."""
    dt = to_year - from_year
    new_dec = dec + pm_dec * dt / 3.6e6
    new_ra = ra + pm_ra_cosdec * dt / 3.6e6 / np.cos(np.radians((dec + new_dec) / 2))
    return float(new_ra % 360.0), float(new_dec)


def mjd_to_year(mjd: float) -> float:
    return float(Time(mjd, format="mjd").decimalyear)


def parse_coordinates(text: str) -> SkyCoord | None:
    """Parse "269.452 4.693", "269.452, 4.693", "17:57:48.5 +04:41:36" or "17h57m48.5s +4d41m36s".

    Returns None when the text does not look like coordinates (so it can be tried as a name).
    """
    cleaned = text.strip().replace(",", " ")
    if not cleaned or not _SEXAGESIMAL.fullmatch(cleaned) or not any(c.isdigit() for c in cleaned):
        return None
    parts = cleaned.split()
    if len(parts) == 2:
        try:
            ra, dec = float(parts[0]), float(parts[1])
        except ValueError:
            pass
        else:
            if not (0 <= ra < 360 and -90 <= dec <= 90):
                raise ValueError("Right Ascension must be 0 to 360 degrees and declination -90 to +90 degrees.")
            return SkyCoord(ra, dec, unit="deg")
    try:
        return SkyCoord(cleaned, unit=(u.hourangle, u.deg))
    except ValueError as exc:
        raise ValueError(f"Could not read '{text}' as coordinates.") from exc


def resolve_name(name: str) -> Target:
    """Look a name up with the CDS Sesame service and move it to VIEW_EPOCH along its proper motion."""
    response = http_get(SESAME_URL + quote(name.strip()), timeout=30, attempts=3)
    root = ET.fromstring(response.content)
    resolver = next((r for r in root.iter("Resolver") if r.find("jradeg") is not None), None)
    if resolver is None:
        raise LookupError(f"No object called '{name}' was found.")
    ra = float(resolver.findtext("jradeg"))
    dec = float(resolver.findtext("jdedeg"))
    pm = resolver.find("pm")
    pm_ra = float(pm.findtext("pmRA", "0")) if pm is not None else 0.0
    pm_dec = float(pm.findtext("pmDE", "0")) if pm is not None else 0.0
    ra_now, dec_now = propagate(ra, dec, pm_ra, pm_dec, CATALOG_EPOCH, VIEW_EPOCH)
    label = (resolver.findtext("oname") or name).replace("NAME ", "").replace("V* ", "").replace("* ", "").strip()
    return Target(label=label, ra=ra_now, dec=dec_now, pm_ra_cosdec=pm_ra, pm_dec=pm_dec, source="SIMBAD via CDS Sesame")


def resolve(text: str) -> Target:
    """Coordinates are used as given (no motion); anything else is looked up as a name."""
    coord = parse_coordinates(text)
    if coord is not None:
        return Target(label=coord.to_string("hmsdms", precision=1), ra=float(coord.ra.deg), dec=float(coord.dec.deg))
    return resolve_name(text)
