from apps.estimation.reeftrace_estimation.demo import classify, make_demo


def test_dual_modes_and_unknown():
    moving = make_demo("moving")["estimate"]
    stationary = make_demo("stationary")["estimate"]
    unknown = make_demo("unknown")["estimate"]
    assert (moving["mode"], moving["source"]) == ("moving", "B")
    assert (stationary["mode"], stationary["source"]) == ("stationary", "A")
    assert unknown["source"] == "Unknown"
    assert moving["synthetic"] is True


def test_short_track_abstains_and_replay_is_repeatable():
    assert classify([{"t": 0, "x": 1, "y": 2}]) == "uncertain"
    assert make_demo("moving") == make_demo("moving")
