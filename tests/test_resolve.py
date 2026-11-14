# AI-generated code: written with Claude (Anthropic) at the team's direction for NASA Space Apps 2026.
import pytest

from spherex.resolve import Target, parse_coordinates, propagate


def test_decimal_degrees():
    c = parse_coordinates("269.452 4.693")
    assert c.ra.deg == pytest.approx(269.452)
    assert c.dec.deg == pytest.approx(4.693)


def test_decimal_degrees_with_comma():
    c = parse_coordinates("269.452, -4.693")
    assert c.dec.deg == pytest.approx(-4.693)


def test_sexagesimal_letters():
    c = parse_coordinates("08h55m10.831s -7d14m42.53s")
    assert c.ra.deg == pytest.approx(133.795129, abs=1e-5)
    assert c.dec.deg == pytest.approx(-7.245147, abs=1e-5)


def test_sexagesimal_colons():
    c = parse_coordinates("17:57:48.5 +04:41:36")
    assert c.ra.deg == pytest.approx(269.452083, abs=1e-5)


@pytest.mark.parametrize("name", ["Barnard's Star", "R Dra", "eps Ind B", "WISE 0855-0714", "RW Aur"])
def test_names_are_not_coordinates(name):
    assert parse_coordinates(name) is None


def test_out_of_range_degrees():
    with pytest.raises(ValueError):
        parse_coordinates("400 10")


def test_propagate_north():
    ra, dec = propagate(10.0, 0.0, 0.0, 3600.0, 2000.0, 2001.0)  # 3.6"/yr north for one year
    assert ra == pytest.approx(10.0)
    assert dec == pytest.approx(0.001)


def test_propagate_ra_uses_cos_dec():
    ra, _ = propagate(10.0, 60.0, 3600.0, 0.0, 2000.0, 2001.0)
    assert ra == pytest.approx(10.0 + 0.001 / 0.5, rel=1e-6)


def test_target_without_motion_does_not_move():
    t = Target(label="x", ra=1.0, dec=2.0)
    assert t.position_at(2030.0) == pytest.approx((1.0, 2.0))
    assert not t.has_motion
