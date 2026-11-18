"""Tests for QuantumDots-Lab: box, shells, blockade, Brus, exchange, gates."""
import math

import pytest

import main as m


# ---- particle in a box
def test_box_ground_energy_value():
    assert m.box_energy_1d_ev(1, 10.0) == pytest.approx(0.056124, abs=1e-5)


def test_box_inverse_L2_scaling():
    assert m.box_energy_1d_ev(1, 5.0) / m.box_energy_1d_ev(1, 10.0) \
        == pytest.approx(4.0, rel=1e-12)
    assert m.box_energy_1d_ev(2, 7.0) / m.box_energy_1d_ev(2, 14.0) \
        == pytest.approx(4.0, rel=1e-12)


def test_box_n_squared():
    e1 = m.box_energy_1d_ev(1, 12.0)
    for n in (2, 3, 4):
        assert m.box_energy_1d_ev(n, 12.0) == pytest.approx(n * n * e1)


def test_box_spacing_monotonic_in_size():
    spacings = [m.box_spacing_1d_ev(1, L) for L in (5.0, 10.0, 20.0, 40.0)]
    assert spacings == sorted(spacings, reverse=True)


def test_box_rejects_bad_inputs():
    with pytest.raises(ValueError):
        m.box_energy_1d_ev(0, 10.0)
    with pytest.raises(ValueError):
        m.box_energy_1d_ev(1, 0.0)


def test_box_3d_degeneracies():
    levels = m.box_levels_3d_ev(10.0)
    assert levels[0][1] == 1 and levels[0][2] == [(1, 1, 1)]
    assert levels[1][1] == 3
    assert levels[2][1] == 3
    assert levels[1][0] / levels[0][0] == pytest.approx(2.0)
    assert levels[2][0] / levels[0][0] == pytest.approx(3.0)


def test_box_report_rows():
    rows = m.box_report()
    assert [r["length_nm"] for r in rows] == [5.0, 10.0, 20.0, 40.0]
    assert rows[0]["spacing_1_to_2_mev"] > rows[-1]["spacing_1_to_2_mev"]


# ---- harmonic shells
def test_magic_numbers_2d():
    rows = m.harmonic_shells_2d()
    assert [r["cumulative_electrons"] for r in rows] == [2, 6, 12, 20]


def test_magic_numbers_3d():
    rows = m.harmonic_shells_3d()
    assert [r["cumulative_electrons"] for r in rows] == [2, 8, 20, 40]


def test_shell_energies():
    assert [r["energy_mev"] for r in m.harmonic_shells_2d()] \
        == [3.0, 6.0, 9.0, 12.0]
    assert m.harmonic_shells_3d()[0]["energy_mev"] == pytest.approx(4.5)


def test_level_ladder():
    assert m.single_particle_levels_mev(count=8) \
        == [3.0, 3.0, 6.0, 6.0, 6.0, 6.0, 9.0, 9.0]


# ---- constant interaction / blockade
def test_charging_energy_value():
    assert m.charging_energy_mev(80.0) == pytest.approx(2.0029, abs=0.005)
    assert m.charging_energy_mev(40.0) == pytest.approx(2.0
                                                        * m.charging_energy_mev(80.0))


def test_thermal_energy():
    assert m.thermal_energy_mev(300.0) == pytest.approx(25.852, abs=0.01)
    with pytest.raises(ValueError):
        m.thermal_energy_mev(0.0)


def test_chemical_potentials():
    ec = m.charging_energy_mev()
    assert m.chemical_potential_mev(1) == pytest.approx(3.0)
    assert m.chemical_potential_mev(2) == pytest.approx(3.0 + ec)
    assert m.chemical_potential_mev(3) == pytest.approx(6.0 + 2 * ec)


def test_addition_energy_sawtooth():
    ec = m.charging_energy_mev()
    assert m.addition_energy_mev(1) == pytest.approx(ec)
    assert m.addition_energy_mev(2) == pytest.approx(ec + 3.0)
    assert m.addition_energy_mev(3) == pytest.approx(ec)
    assert m.addition_energy_mev(6) == pytest.approx(ec + 3.0)


def test_total_energy_telescoping():
    total = sum(m.chemical_potential_mev(n) for n in range(1, 9))
    assert m.total_energy_mev(8) == pytest.approx(total)


def test_blockade_ratios():
    rep = m.blockade_report()
    rows = {r["temp_k"]: r for r in rep["rows"]}
    assert rows[0.1]["ec_over_kt"] > 200.0
    assert rows[300.0]["ec_over_kt"] < 1.0
    assert rows[0.1]["blockaded"] and not rows[300.0]["blockaded"]


def test_stability_windows_tile_and_widths():
    win = m.stability_windows()
    for a, b in zip(win, win[1:]):
        assert a["v_high_mv"] == pytest.approx(b["v_low_mv"])
    for w in win:
        if w["n_electrons"] >= 1:
            assert w["width_mev"] == pytest.approx(
                m.addition_energy_mev(w["n_electrons"]))
    assert win[2]["width_mv"] > win[1]["width_mv"]


# ---- Brus emission
def test_brus_monotonic():
    radii = [2.0, 3.0, 4.0, 5.0, 6.0]
    gaps = [m.brus_gap_ev(r) for r in radii]
    waves = [m.emission_wavelength_nm(r) for r in radii]
    assert gaps == sorted(gaps, reverse=True)
    assert waves == sorted(waves)


def test_brus_values():
    assert m.brus_gap_ev(2.0) == pytest.approx(2.542, abs=0.01)
    assert m.brus_gap_ev(6.0) == pytest.approx(1.797, abs=0.01)
    assert m.emission_wavelength_nm(2.0) < m.emission_wavelength_nm(6.0)


def test_brus_above_bulk_and_bohr_radius():
    for r in (2.0, 4.0, 6.0, 10.0):
        assert m.brus_gap_ev(r) > m.CDSE_PARAMS["bulk_gap_ev"]
    assert m.exciton_bohr_radius_nm() == pytest.approx(5.35, abs=0.05)


def test_brus_rejects_bad_radius():
    with pytest.raises(ValueError):
        m.brus_gap_ev(0.0)


# ---- two-electron toy
def test_exchange_splitting():
    st = m.two_electron_states()
    assert st["singlet_triplet_splitting_mev"] == pytest.approx(2 * m.K01_MEV)
    assert st["open_triplet_01"] < st["open_singlet_01"]


def test_two_electron_energies():
    st = m.two_electron_states()
    assert st["closed_singlet_00"] == pytest.approx(8.0)
    assert st["open_singlet_01"] == pytest.approx(10.90)
    assert st["open_triplet_01"] == pytest.approx(10.20)
    assert st["closed_singlet_11"] == pytest.approx(13.35)


def test_jacobi_solver():
    vals, _ = m._sorted_eig([[2.0, 1.0], [1.0, 2.0]])
    assert vals == pytest.approx([1.0, 3.0])
    vals3, vecs3 = m._sorted_eig(m.singlet_ci_matrix())
    mat = m.singlet_ci_matrix()
    for i in range(3):
        for j in range(3):
            rebuilt = sum(vecs3[i][k] * vals3[k] * vecs3[j][k]
                          for k in range(3))
            assert rebuilt == pytest.approx(mat[i][j], abs=1e-9)


def test_ci_ground_state():
    ci = m.singlet_ci()
    assert ci["ground_energy_mev"] < 8.0
    assert 0.01 < ci["ci_lowering_mev"] < 0.10
    assert ci["ground_config_weights"][0] > 0.95
    assert sum(ci["ground_config_weights"]) == pytest.approx(1.0, abs=1e-5)


# ---- classifier
def test_classifier_scenarios():
    rep = m.classifier_report()
    assert rep["dilution_fridge_shell_closure_N2"] == "shell-filling"
    assert rep["dilution_fridge_mid_shell_N3"] == "coulomb-blockaded"
    assert rep["room_temperature_N4"] == "open"


def test_classifier_model_rules():
    assert m.model_label(0.5, 1.5, 2) == "open"
    assert m.model_label(100.0, 1.5, 6) == "shell-filling"
    assert m.model_label(100.0, 0.2, 3) == "coulomb-blockaded"
    assert len(m.TRAINING_GRID) == 432


# ---- council + gates + CLI
def test_council_seats():
    brains = m.brains_report()
    assert brains["decider"]["seat"] == "Gemini Argon 4 Extended Thinking"
    assert brains["decider"]["role"] == "DECIDER"
    assert brains["decider"]["can_override_hold"] is False
    assert brains["advisor"]["can_override_hold"] is False
    assert brains["flow"]["rendered"] is False
    assert brains["flow"]["live"] == 0
    assert len(brains["decider"]["trace_sha256_16"]) == 16


def test_hold_gates():
    assert len(m.HOLD_GATES) == 14
    for action in m.HOLD_GATES:
        assert m.gate(action) == "HOLD"
    assert m.gate("run_demo_simulation") == "PROCEED"


def test_hold_demo_exit_2():
    assert m.main(["hold-demo"]) == 2
    assert m.main(["hold-demo", "qubit_performance_claim"]) == 2
    assert m.main(["hold-demo", "run_demo_simulation"]) == 0


def test_checks_all_pass():
    checks = m.run_checks()
    assert all(ok for _, ok in checks), [n for n, ok in checks if not ok]
    assert len(checks) >= 50


def test_cli_json_commands(capsys):
    for cmd in ("box", "shells", "blockade", "emission", "exchange",
                "classify", "brains"):
        assert m.main([cmd]) == 0
    out = capsys.readouterr().out
    assert "charging_energy_mev" in out
    assert "singlet_triplet_splitting_mev" in out


def test_demo_exit_zero(capsys):
    assert m.main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "CHECKS" in out and "VERDICT PROCEED" in out
