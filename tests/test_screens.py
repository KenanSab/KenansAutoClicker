"""Saved coordinates surviving a display change.

Clicking in the wrong place after a resolution change or an unplugged monitor
is the most reported auto clicker failure there is, and it is silent: the
coordinates are still valid numbers, they just no longer mean anything.
"""

import pytest

from kenansautoclicker.screens import (describe, geometry_changed,
                                       looks_offscreen, scale_points)


# ------------------------------------------------------------- change check --
def test_same_geometry_is_not_a_change():
    assert not geometry_changed([1920, 1080], (1920, 1080))


def test_different_geometry_is_a_change():
    assert geometry_changed([1920, 1080], (2560, 1440))


def test_missing_geometry_is_not_treated_as_a_change():
    """Points saved before this existed have no geometry. That is not an error,
    so it must not produce a scary warning."""
    assert not geometry_changed(None, (1920, 1080))
    assert not geometry_changed([], (1920, 1080))
    assert not geometry_changed([0, 0], (1920, 1080))


# -------------------------------------------------------------------- scale --
def test_scaling_maps_proportionally():
    pts = scale_points([(960, 540)], [1920, 1080], (3840, 2160))
    assert pts == [(1920, 1080)]


def test_scaling_down():
    pts = scale_points([(1920, 1080)], [1920, 1080], (960, 540))
    assert pts == [(960, 540)]


def test_scaling_is_a_no_op_when_nothing_changed():
    pts = [(10, 20), (30, 40)]
    assert scale_points(pts, [1920, 1080], (1920, 1080)) == pts


def test_scaling_handles_a_corner_point():
    assert scale_points([(0, 0)], [1920, 1080], (1280, 720)) == [(0, 0)]


def test_scaling_never_divides_by_zero():
    assert scale_points([(5, 5)], [0, 0], (100, 100)) == [(5, 5)]


# --------------------------------------------------------------- off-screen --
def test_points_inside_are_not_flagged():
    assert looks_offscreen([(10, 10), (500, 500)], (1920, 1080)) == []


def test_points_outside_are_flagged():
    off = looks_offscreen([(3000, 500)], (1920, 1080))
    assert off == [(3000, 500)]


def test_negative_points_are_flagged():
    """A monitor placed to the left gives negative coordinates."""
    assert looks_offscreen([(-800, 400)], (1920, 1080)) == [(-800, 400)]


def test_offscreen_needs_a_known_screen():
    assert looks_offscreen([(1, 1)], (0, 0)) == []


# ------------------------------------------------------------------ message --
def test_no_message_when_all_is_well():
    assert describe([(10, 10)], [1920, 1080], (1920, 1080)) is None


def test_no_message_without_points():
    assert describe([], [1920, 1080], (800, 600)) is None


def test_resolution_change_offers_a_rescale():
    msg, can_rescale = describe([(10, 10)], [1920, 1080], (2560, 1440))
    assert can_rescale is True
    assert "1920x1080" in msg and "2560x1440" in msg


def test_offscreen_point_warns_without_offering_a_rescale():
    """A second monitor is a legitimate reason to be off the primary screen,
    so this informs rather than offering to 'fix' a non-problem."""
    msg, can_rescale = describe([(3000, 10)], [1920, 1080], (1920, 1080))
    assert can_rescale is False
    assert "outside" in msg.lower()


# ------------------------------------------------------------ app behaviour --
def test_capturing_a_point_records_the_screen(app):
    app.vars["target_mode"].set("Fixed")
    app._got_point(100, 200, "Fixed")
    assert app.points_geometry is not None
    assert len(app.points_geometry) == 2


def test_clearing_points_clears_the_geometry(app):
    app._got_point(100, 200, "Fixed")
    app._clear_points()
    assert app.points == [] and app.points_geometry is None


def test_geometry_survives_a_config_round_trip(app):
    app._got_point(100, 200, "Fixed")
    saved = list(app.points_geometry)
    data = app._collect()
    app.points_geometry = None
    app._apply(data)
    assert app.points_geometry == saved


def test_rescaling_moves_the_points(app):
    app.points = [(100, 100)]
    app.points_geometry = [200, 200]           # pretend a much smaller screen
    app.vars["target_mode"].set("Multi")
    app._rescale_points()
    now = app.points_geometry
    assert app.points[0][0] == pytest.approx(100 * now[0] / 200, abs=2)
    assert app.points_geometry != [200, 200]


def test_stale_geometry_produces_a_warning(app):
    app.points = [(10, 10)]
    app.points_geometry = [123, 456]           # nothing like a real screen
    assert app._point_warning() is not None


def test_matching_geometry_produces_no_warning(app):
    from kenansautoclicker.screens import current_geometry
    app.points = [(5, 5)]
    app.points_geometry = list(current_geometry(app.root))
    assert app._point_warning() is None
