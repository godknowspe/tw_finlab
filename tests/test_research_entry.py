import numpy as np
import pytest

from research.entry_timing import sim


def series(*legs):
    """Piecewise-linear price path through the given prices, 21 sessions per leg."""
    out = [legs[0]]
    for a, b in zip(legs, legs[1:]):
        out += list(np.linspace(a, b, 22)[1:])
    return np.array(out, dtype=float)


def one_window(px, H):
    starts, first = sim.windows(px, H, step=len(px))            # a single window at index 0
    assert list(starts) == [0]
    return starts, first


def test_a_dip_that_never_comes_leaves_cash_idle_and_loses_to_lump_in_a_rising_market():
    px = series(100, 120, 150)
    H = len(px) - 1
    starts, first = one_window(px, H)
    assert (first == -1).all()
    final = sim.dip(px, first, starts, H, upfront=0.0, step=0.10, tranches=2)
    assert final[0] == pytest.approx(1.0)                        # still all cash
    assert sim.lump(px, starts, H)[0] == pytest.approx(1.5)


def test_tranches_buy_at_the_first_session_the_drawdown_is_reached():
    px = series(100, 100, 80, 120)                               # falls 20%, then recovers to 120
    H = len(px) - 1
    starts, first = one_window(px, H)
    k10, k20 = first[0, 1], first[0, 3]                          # LEVELS: 0.05, 0.10, 0.15, 0.20
    assert 21 < k10 < k20 <= 42 and px[k10] <= 90 + 1e-9 and px[k10 - 1] > 90
    final = sim.dip(px, first, starts, H, upfront=0.0, step=0.10, tranches=2)
    expected = 0.5 * 120 / px[k10] + 0.5 * 120 / px[k20]
    assert final[0] == pytest.approx(expected)
    assert final[0] > sim.lump(px, starts, H)[0]                 # waiting for the dip paid off here


def test_drawdown_is_measured_from_the_running_peak_since_the_window_start():
    px = series(100, 130, 117)                                   # -10% from the 130 peak, not from the start
    H = len(px) - 1
    _, first = one_window(px, H)
    assert first[0, 1] == H                                      # 10% level only at the very end
    assert first[0, 3] == -1


def test_deadline_forces_untriggered_tranches_in_and_never_after_the_horizon():
    px = series(100, 110, 140)
    H = len(px) - 1
    starts, first = one_window(px, H)
    final = sim.dip(px, first, starts, H, upfront=0.0, step=0.10, tranches=1, deadline_months=1)
    assert final[0] == pytest.approx(140 / px[21])               # bought on day 21 instead of waiting forever
    final_far = sim.dip(px, first, starts, H, upfront=0.0, step=0.10, tranches=1, deadline_months=99)
    assert final_far[0] == pytest.approx(140 / px[H])            # the deadline is capped at the horizon


def test_idle_cash_earns_the_rate_only_while_it_waits():
    px = series(100, 100, 100)
    H = len(px) - 1
    starts, first = one_window(px, H)
    final = sim.dip(px, first, starts, H, upfront=0.0, step=0.10, tranches=1, rate=0.05)
    assert final[0] == pytest.approx(1.05 ** (H / 252))


def test_spreading_equals_lump_on_a_flat_path_and_beats_it_when_prices_fall():
    flat = series(100, 100, 100, 100, 100, 100, 100)
    H = len(flat) - 1
    s, _ = one_window(flat, H)
    assert sim.spread(flat, s, H, months=6)[0] == pytest.approx(1.0)
    fall = series(100, 70, 70, 70, 70, 70, 70)
    s, _ = one_window(fall, len(fall) - 1)
    assert sim.spread(fall, s, len(fall) - 1, months=6)[0] > sim.lump(fall, s, len(fall) - 1)[0]
    with pytest.raises(ValueError):
        sim.spread(fall, s, 40, months=6)                         # 6 months cannot fit in 40 sessions


def test_compare_reports_win_rate_and_splits_up_and_down_windows():
    base = np.array([1.2, 1.1, 0.8, 0.9])
    final = np.array([1.1, 1.0, 0.9, 1.0])
    c = sim.compare(final, base)
    assert c["win"] == 0.5 and c["n_up"] == 2 and c["n_down"] == 2
    assert c["win_when_up"] == 0.0 and c["win_when_down"] == 1.0
    assert c["worst"] == pytest.approx(1.0 / 1.1 - 1)           # -9.09%: second window
    assert c["best"] == pytest.approx(0.9 / 0.8 - 1)            # +12.5%: third window
