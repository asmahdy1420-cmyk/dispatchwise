from __future__ import annotations

import pytest

from conftest import loc
from dispatchwise.geo import haversine_km, nearest_neighbour_order, path_length_km
from dispatchwise.traffic import TrafficProfile


def test_haversine_known_distance():
    # Doha (Corniche) to Al Wakrah is roughly 15 km as the crow flies.
    doha, wakrah = loc(25.2854, 51.5310), loc(25.1715, 51.6034)
    assert haversine_km(doha, wakrah) == pytest.approx(14.6, abs=0.5)
    assert haversine_km(doha, doha) == 0.0


def test_haversine_is_symmetric_and_degree_of_latitude_is_111km():
    a, b = loc(0, 0), loc(1, 0)
    assert haversine_km(a, b) == pytest.approx(111.2, abs=0.1)
    assert haversine_km(a, b) == pytest.approx(haversine_km(b, a))


def test_nearest_neighbour_visits_closest_first():
    start = loc(0, 0)
    stops = [loc(0, 0.3), loc(0, 0.1), loc(0, 0.2)]
    order = nearest_neighbour_order(start, stops)
    assert order == [1, 2, 0]
    assert path_length_km([start, *[stops[i] for i in order]]) == pytest.approx(
        haversine_km(start, stops[0])
    )


def test_traffic_profile_defaults_and_overrides():
    profile = TrafficProfile({3: 0.5})
    assert profile.multiplier(18) > profile.multiplier(10) > profile.multiplier(3)
    assert profile.multiplier(3) == 0.5
    assert profile.multiplier(27) == profile.multiplier(3)


def test_traffic_profile_rejects_bad_values():
    with pytest.raises(ValueError):
        TrafficProfile({24: 1.0})
    with pytest.raises(ValueError):
        TrafficProfile({8: 0})
