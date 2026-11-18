#!/usr/bin/env python3
"""QuantumDots-Lab - educational quantum-dot confinement + charging lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Education only - and the scope is stated up front:

  * Every number in this lab comes from a TEXTBOOK model with
    LABELLED parameters: a particle in a box, a 2D/3D harmonic
    oscillator (Fock-Darwin at zero field), the constant-interaction
    model of Coulomb blockade, the Brus equation for confinement-
    shifted emission, and a two-electron singlet/triplet toy built
    from Slater-Condon rules in miniature.
  * Labelled parameters (a GaAs effective mass, a CdSe bulk gap, a
    dot capacitance, Coulomb integrals) are teaching values in the
    published textbook ranges - they are NOT measurements of any
    real device, and no output of this lab is a device spec.
  * Nothing here fabricates, grows, etches, wires, cools, or biases
    a real quantum dot. Fabrication, device operation, product,
    qubit-performance, and measured-data claims are permanent HOLD
    gates - with Gemini Argon 4 Extended Thinking as DECIDER
    (names-only, tighten-only), Muse as advisor (never overrides
    HOLD), and Google Flow plan-only seats.
"""
import hashlib
import json
import math
import sys

# ---------------------------------------------------------------- constants
VERSION = "1.0.0"

# Physical constants (SI, exact or CODATA-class teaching values).
HBAR = 1.054571817e-34          # J s
M_E = 9.1093837015e-31          # kg
E_CHARGE = 1.602176634e-19      # C (exact)
EPS_0 = 8.8541878128e-12        # F/m
K_B = 1.380649e-23              # J/K (exact)
EV_J = E_CHARGE                 # 1 eV in joules
HC_EV_NM = 1239.841984          # eV nm
A_0_NM = 0.0529177              # Bohr radius, nm
# hbar^2 / (2 m_e) in eV nm^2 - the confinement scale of the whole lab.
HBAR2_2ME_EV_NM2 = 0.0380998212
# e^2 / (4 pi eps_0) in eV nm.
E2_4PIEPS0_EV_NM = 1.439964485

# Labelled material parameters - textbook-class teaching values,
# flagged LABELLED everywhere they are used. Not device data.
GAAS_M_EFF = 0.067              # GaAs electron effective mass / m_e (LABELLED)
CDSE_PARAMS = {                 # CdSe Brus parameters (LABELLED)
    "bulk_gap_ev": 1.74,
    "m_e_eff": 0.13,
    "m_h_eff": 0.45,
    "eps_r": 10.2,
}
HW_MEV = 3.0                    # harmonic confinement hbar*omega, meV (LABELLED)
DOT_CAPACITANCE_AF = 80.0       # dot total capacitance, aF (LABELLED)
GATE_LEVER_ARM = 0.10           # gate lever arm alpha (LABELLED)
# Labelled two-electron Coulomb integrals, meV (see section 5).
J00_MEV = 2.00                  # direct integral, both electrons in orbital 0
J11_MEV = 1.35                  # direct integral, both electrons in orbital 1
J01_MEV = 1.55                  # direct integral, one electron in each
K01_MEV = 0.35                  # exchange integral between orbitals 0 and 1
PAIR_HOP_MEV = 0.45             # <00|V|11> pair-scattering integral
MIX_0111_MEV = 0.28             # <(0,1)S|H|11> labelled coupling

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "fabrication_claim": "HOLD - no fabrication guidance or claim; this lab grows, etches, and deposits nothing",
    "real_device_control": "HOLD - no control of a real quantum dot, gate electrode, or cryostat",
    "material_synthesis_guidance": "HOLD - no synthesis recipes for quantum-dot materials or precursors",
    "single_electron_product_claim": "HOLD - no single-electron transistor product, yield, or reliability claim",
    "qubit_performance_claim": "HOLD - no qubit coherence, fidelity, or readout claim from a textbook model",
    "display_product_claim": "HOLD - no QD display brightness, lifetime, or product claim",
    "medical_imaging_claim": "HOLD - no medical imaging, bio-labelling, or in-vivo claim for any dot",
    "solar_product_claim": "HOLD - no solar-cell efficiency or product claim from the Brus model",
    "cryogenic_operation_live": "HOLD - no live cryogenic operation directed from a simulation",
    "gate_voltage_live_application": "HOLD - no applying gate or bias voltages to real hardware",
    "measured_device_data_claim": "HOLD - simulated numbers must never be presented as measured device data",
    "investment_claim": "HOLD - no investment claim; a teaching model is not a prospectus",
    "patent_claim": "HOLD - no patentability or novelty claim for textbook models",
    "textbook_model_as_device_spec": "HOLD - labelled parameters must never be presented as a real device's specification",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. Particle in a box
# The simplest confinement there is: an electron in an infinite well
# of width L. E_n = n^2 pi^2 hbar^2 / (2 m* L^2). The level spacing
# grows like 1/L^2 - halve the dot and the spacing quadruples. That
# single scaling law is why "quantum" shows up at the nanoscale.

def box_energy_1d_ev(n, length_nm, m_eff=GAAS_M_EFF):
    """1D infinite-well level energy in eV (n = 1, 2, 3, ...)."""
    if n < 1 or length_nm <= 0 or m_eff <= 0:
        raise ValueError("need n >= 1, L > 0, m* > 0")
    return n * n * math.pi ** 2 * HBAR2_2ME_EV_NM2 / (m_eff * length_nm ** 2)


def box_spacing_1d_ev(n, length_nm, m_eff=GAAS_M_EFF):
    """Spacing E_{n+1} - E_n of the 1D well, in eV."""
    return (box_energy_1d_ev(n + 1, length_nm, m_eff)
            - box_energy_1d_ev(n, length_nm, m_eff))


def box_levels_3d_ev(length_nm, m_eff=GAAS_M_EFF, max_sum=6):
    """3D cubic-box levels grouped by energy, with degeneracies.

    Returns a list of (energy_ev, degeneracy, [quantum-number triples])
    sorted by energy, for n_x + n_y + n_z <= max_sum + 2.
    """
    groups = {}
    for nx in range(1, max_sum + 1):
        for ny in range(1, max_sum + 1):
            for nz in range(1, max_sum + 1):
                if nx + ny + nz > max_sum + 2:
                    continue
                key = nx * nx + ny * ny + nz * nz
                groups.setdefault(key, []).append((nx, ny, nz))
    unit = math.pi ** 2 * HBAR2_2ME_EV_NM2 / (m_eff * length_nm ** 2)
    levels = []
    for key in sorted(groups):
        triples = sorted(groups[key])
        levels.append((key * unit, len(triples), triples))
    return levels


def box_report():
    rows = []
    for length in (5.0, 10.0, 20.0, 40.0):
        rows.append({
            "length_nm": length,
            "e1_mev": box_energy_1d_ev(1, length) * 1000.0,
            "spacing_1_to_2_mev": box_spacing_1d_ev(1, length) * 1000.0,
            "spacing_2_to_3_mev": box_spacing_1d_ev(2, length) * 1000.0,
        })
    return rows


# ================================================================ 2. Harmonic confinement + shells
# A smooth dot is closer to a harmonic bowl than a hard box:
# E = hbar*omega*(n_x + n_y + 1) in 2D (Fock-Darwin at B = 0). Levels
# bunch into shells; with spin, the 2D shell closures land on the
# magic numbers 2, 6, 12, 20 - the artificial-atom periodic table.

def harmonic_shells_2d(hw_mev=HW_MEV, shells=4):
    """2D harmonic shells: energy, orbital degeneracy, spin capacity,
    cumulative electron count (the magic numbers)."""
    rows = []
    cumulative = 0
    for s in range(shells):
        orbitals = s + 1
        capacity = 2 * orbitals
        cumulative += capacity
        rows.append({
            "shell": s,
            "energy_mev": (s + 1) * hw_mev,
            "orbitals": orbitals,
            "spin_capacity": capacity,
            "cumulative_electrons": cumulative,
        })
    return rows


def harmonic_shells_3d(hw_mev=HW_MEV, shells=4):
    """3D harmonic shells: degeneracy (s+1)(s+2)/2 orbitals x2 spin."""
    rows = []
    cumulative = 0
    for s in range(shells):
        orbitals = (s + 1) * (s + 2) // 2
        capacity = 2 * orbitals
        cumulative += capacity
        rows.append({
            "shell": s,
            "energy_mev": (s + 1.5) * hw_mev,
            "orbitals": orbitals,
            "spin_capacity": capacity,
            "cumulative_electrons": cumulative,
        })
    return rows


def single_particle_levels_mev(hw_mev=HW_MEV, count=12):
    """Spin-resolved 2D harmonic level ladder, lowest `count` electrons
    worth of single-particle energies (each spatial orbital twice)."""
    levels = []
    s = 0
    while len(levels) < count:
        for _ in range(2 * (s + 1)):
            levels.append((s + 1) * hw_mev)
        s += 1
    return levels[:count]


# ================================================================ 3. Constant-interaction model
# The workhorse of Coulomb blockade: the dot is a metal island with
# total capacitance C. Adding one electron costs the single-particle
# level plus the charging energy E_C = e^2 / C, and the addition
# energy E_add(N) = mu(N+1) - mu(N) = level spacing + E_C. When
# E_C >> kT, current is blockaded except at gate voltages where two
# charge states are degenerate - the stability diagram.

def charging_energy_mev(capacitance_af=DOT_CAPACITANCE_AF):
    """E_C = e^2 / C in meV, from SI constants (C labelled, in aF)."""
    cap_f = capacitance_af * 1e-18
    return E_CHARGE ** 2 / cap_f / EV_J * 1000.0


def thermal_energy_mev(temp_k):
    """kT in meV."""
    if temp_k <= 0:
        raise ValueError("temperature must be positive")
    return K_B * temp_k / EV_J * 1000.0


def total_energy_mev(n_elec, hw_mev=HW_MEV, capacitance_af=DOT_CAPACITANCE_AF):
    """U(N) = sum of occupied single-particle levels + E_C N(N-1)/2."""
    if n_elec < 0:
        raise ValueError("N must be >= 0")
    levels = single_particle_levels_mev(hw_mev, max(n_elec, 1))
    ec = charging_energy_mev(capacitance_af)
    return sum(levels[:n_elec]) + ec * n_elec * (n_elec - 1) / 2.0


def chemical_potential_mev(n_elec, hw_mev=HW_MEV,
                           capacitance_af=DOT_CAPACITANCE_AF):
    """mu(N) = U(N) - U(N-1): the price of the Nth electron."""
    if n_elec < 1:
        raise ValueError("mu(N) needs N >= 1")
    return (total_energy_mev(n_elec, hw_mev, capacitance_af)
            - total_energy_mev(n_elec - 1, hw_mev, capacitance_af))


def addition_energy_mev(n_elec, hw_mev=HW_MEV,
                        capacitance_af=DOT_CAPACITANCE_AF):
    """E_add(N) = mu(N+1) - mu(N) = level spacing + E_C."""
    return (chemical_potential_mev(n_elec + 1, hw_mev, capacitance_af)
            - chemical_potential_mev(n_elec, hw_mev, capacitance_af))


def blockade_report(temps_k=(0.1, 4.2, 77.0, 300.0),
                    capacitance_af=DOT_CAPACITANCE_AF):
    """E_C / kT across temperatures: blockade needs the ratio >> 1."""
    ec = charging_energy_mev(capacitance_af)
    rows = []
    for temp in temps_k:
        kt = thermal_energy_mev(temp)
        rows.append({
            "temp_k": temp,
            "kt_mev": kt,
            "ec_over_kt": ec / kt,
            "blockaded": ec / kt > 10.0,
        })
    return {"charging_energy_mev": ec, "rows": rows}


def stability_windows(n_max=8, hw_mev=HW_MEV,
                      capacitance_af=DOT_CAPACITANCE_AF,
                      lever_arm=GATE_LEVER_ARM):
    """Gate-voltage windows where the electron number N is fixed.

    With lever arm alpha, the gate moves mu by e*alpha*V_g; charge
    state N is stable between the mu(N) and mu(N+1) degeneracy
    points. Voltages are in mV (mu in meV / alpha).
    """
    rows = []
    for n in range(0, n_max + 1):
        mu_low = (chemical_potential_mev(n, hw_mev, capacitance_af)
                  if n >= 1 else 0.0)
        mu_high = chemical_potential_mev(n + 1, hw_mev, capacitance_af)
        rows.append({
            "n_electrons": n,
            "v_low_mv": mu_low / lever_arm,
            "v_high_mv": mu_high / lever_arm,
            "width_mv": (mu_high - mu_low) / lever_arm,
            "width_mev": mu_high - mu_low,
        })
    return rows


# ================================================================ 4. Brus emission model
# Strong confinement shifts the band gap up: the Brus equation adds
# the electron + hole box energies, subtracts the screened Coulomb
# attraction, and subtracts a small polarisation term. Smaller dot
# -> bigger gap -> bluer photon. The parameters are LABELLED CdSe
# textbook values; the model's limits are stated in the demo: it is
# a strong-confinement estimate that over-shifts at very small R
# and ignores finite barriers, surface states, and phonon coupling.

def brus_gap_ev(radius_nm, params=None):
    """Brus-equation gap in eV for a spherical dot of radius R (nm)."""
    p = params or CDSE_PARAMS
    if radius_nm <= 0:
        raise ValueError("radius must be positive")
    confinement = (math.pi ** 2 * HBAR2_2ME_EV_NM2 / radius_nm ** 2
                   * (1.0 / p["m_e_eff"] + 1.0 / p["m_h_eff"]))
    coulomb = 1.8 * E2_4PIEPS0_EV_NM / (p["eps_r"] * radius_nm)
    mu = 1.0 / (1.0 / p["m_e_eff"] + 1.0 / p["m_h_eff"])
    ry_star = 13.605693 * mu / p["eps_r"] ** 2
    polarisation = 0.248 * ry_star
    return p["bulk_gap_ev"] + confinement - coulomb - polarisation


def emission_wavelength_nm(radius_nm, params=None):
    """Emission wavelength in nm from the Brus gap (lambda = hc / E)."""
    return HC_EV_NM / brus_gap_ev(radius_nm, params)


def exciton_bohr_radius_nm(params=None):
    """Exciton Bohr radius a_B = eps_r * (m_e / mu) * a_0, in nm."""
    p = params or CDSE_PARAMS
    mu = 1.0 / (1.0 / p["m_e_eff"] + 1.0 / p["m_h_eff"])
    return p["eps_r"] / mu * A_0_NM


def brus_report(radii_nm=(2.0, 3.0, 4.0, 5.0, 6.0)):
    rows = []
    for r in radii_nm:
        rows.append({
            "radius_nm": r,
            "gap_ev": brus_gap_ev(r),
            "wavelength_nm": emission_wavelength_nm(r),
            "regime": ("strong" if r < exciton_bohr_radius_nm()
                       else "weak"),
        })
    return {"exciton_bohr_radius_nm": exciton_bohr_radius_nm(),
            "bulk_wavelength_nm": HC_EV_NM / CDSE_PARAMS["bulk_gap_ev"],
            "rows": rows}


# ================================================================ 5. Two-electron toy
# Two electrons in the harmonic dot, in miniature: spatial orbitals
# 0 (shell 0) and 1 (shell 1, one representative). Slater-Condon
# rules by hand: a closed-shell pair costs 2*eps + J; an open-shell
# pair costs eps_0 + eps_1 + J_01 +/- K_01 - PLUS for the singlet,
# MINUS for the triplet, so the triplet sits 2*K_01 lower. A small
# configuration-interaction (CI) matrix over the three singlet
# configurations is diagonalised with a from-scratch Jacobi solver:
# mixing can only lower the ground state (variational principle).

def _jacobi_eig(matrix, tol=1e-12, max_sweeps=100):
    """Eigenvalues + eigenvectors of a real symmetric matrix.

    Cyclic Jacobi rotations; returns (values, vectors) with vectors
    as columns (vectors[row][col]). Deterministic sweep order.
    """
    n = len(matrix)
    a = [row[:] for row in matrix]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(max_sweeps):
        off = math.sqrt(sum(a[i][j] ** 2
                            for i in range(n) for j in range(n) if i != j))
        if off < tol:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-15:
                    continue
                theta = 0.5 * math.atan2(2.0 * a[p][q], a[q][q] - a[p][p])
                c, s = math.cos(theta), math.sin(theta)
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p] = c * akp - s * akq
                    a[k][q] = s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k] = c * apk - s * aqk
                    a[q][k] = s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p] = c * vkp - s * vkq
                    v[k][q] = s * vkp + c * vkq
    return [a[i][i] for i in range(n)], v


def _sorted_eig(matrix):
    vals, vecs = _jacobi_eig(matrix)
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    return ([vals[i] for i in order],
            [[vecs[r][i] for i in order] for r in range(len(vals))])


def two_electron_states(hw_mev=HW_MEV):
    """Hand-built Slater-Condon energies (meV) for the 2-electron toy."""
    eps0 = hw_mev           # 2D shell-0 orbital energy (s+1)*hw, s = 0
    eps1 = 2.0 * hw_mev     # shell-1 representative orbital
    closed_singlet = 2.0 * eps0 + J00_MEV
    open_singlet = eps0 + eps1 + J01_MEV + K01_MEV
    open_triplet = eps0 + eps1 + J01_MEV - K01_MEV
    upper_closed = 2.0 * eps1 + J11_MEV
    return {
        "eps0_mev": eps0,
        "eps1_mev": eps1,
        "closed_singlet_00": closed_singlet,
        "open_singlet_01": open_singlet,
        "open_triplet_01": open_triplet,
        "closed_singlet_11": upper_closed,
        "singlet_triplet_splitting_mev": open_singlet - open_triplet,
    }


def singlet_ci_matrix(hw_mev=HW_MEV):
    """3x3 CI matrix over singlet configurations |00>, |(0,1)S>, |11>.

    Diagonal entries are the Slater-Condon energies. The |00>-|(0,1)S>
    coupling is exactly zero by parity (odd integrand over a symmetric
    well); pair hopping couples |00>-|11>, and a labelled coupling
    mixes |(0,1)S>-|11>.
    """
    st = two_electron_states(hw_mev)
    return [
        [st["closed_singlet_00"], 0.0, PAIR_HOP_MEV],
        [0.0, st["open_singlet_01"], MIX_0111_MEV],
        [PAIR_HOP_MEV, MIX_0111_MEV, st["closed_singlet_11"]],
    ]


def singlet_ci(hw_mev=HW_MEV):
    """Diagonalise the singlet CI matrix; report energies + ground mix."""
    mat = singlet_ci_matrix(hw_mev)
    vals, vecs = _sorted_eig(mat)
    ground_weights = [round(vecs[r][0] ** 2, 6) for r in range(3)]
    return {
        "energies_mev": vals,
        "ground_energy_mev": vals[0],
        "ground_config_weights": ground_weights,
        "ci_lowering_mev": mat[0][0] - vals[0],
    }


# ================================================================ 6. kNN regime classifier
# Features: E_C / kT (blockade strength), level spacing / E_C (shell
# resolution), and electron number N. The training grid is labelled
# by the lab's own regime model below - the classifier interpolates
# the model, it does not replace the constant-interaction arithmetic.

MAGIC_NUMBERS_2D = (2, 6, 12, 20)


def model_label(ec_over_kt, spacing_ratio, n_elec):
    """The regime model distilled to a three-way teaching label."""
    if ec_over_kt < 3.0:
        return "open"
    if n_elec in MAGIC_NUMBERS_2D and spacing_ratio >= 0.8:
        return "shell-filling"
    return "coulomb-blockaded"


def _training_grid():
    rows = []
    for ratio in (0.05, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0):
        for spacing in (0.0, 0.25, 0.5, 1.0, 1.5, 2.5):
            for n_elec in (1, 2, 3, 4, 5, 6, 8, 10, 12):
                rows.append(((ratio, spacing, n_elec),
                             model_label(ratio, spacing, n_elec)))
    return rows


TRAINING_GRID = _training_grid()


def _scaled(features):
    # log10 for the ratio (it spans decades), and N scaled tightly:
    # the charge state is the sharpest feature - one electron changes
    # the regime, so neighbour distance must feel it.
    ratio, spacing, n_elec = features
    return (math.log10(ratio) / 2.5, spacing / 2.5, n_elec / 6.0)


def classify_dot(ec_over_kt, spacing_ratio, n_elec, k=5):
    """kNN over the model-labelled grid, deterministic tie-breaking."""
    target = _scaled((ec_over_kt, spacing_ratio, n_elec))
    ranked = []
    for features, label in TRAINING_GRID:
        point = _scaled(features)
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(target, point)))
        ranked.append((dist, features, label))
    ranked.sort(key=lambda row: (row[0], row[1]))
    votes = {}
    for _, _, label in ranked[:k]:
        votes[label] = votes.get(label, 0) + 1
    priority = {"shell-filling": 0, "coulomb-blockaded": 1, "open": 2}
    return sorted(votes.items(), key=lambda kv: (-kv[1], priority[kv[0]]))[0][0]


def classifier_report():
    ec = charging_energy_mev()
    scenarios = {
        "dilution_fridge_shell_closure_N2": (
            ec / thermal_energy_mev(0.1), HW_MEV / ec, 2),
        "dilution_fridge_mid_shell_N3": (
            ec / thermal_energy_mev(0.1), HW_MEV / ec, 3),
        "helium_bath_4K_mid_shell_N5": (
            ec / thermal_energy_mev(4.2), 0.4, 5),
        "room_temperature_N4": (
            ec / thermal_energy_mev(300.0), HW_MEV / ec, 4),
        "liquid_nitrogen_77K_N6": (
            ec / thermal_energy_mev(77.0), HW_MEV / ec, 6),
    }
    return {name: classify_dot(*features)
            for name, features in scenarios.items()}


# ================================================================ 7. Advisory seats
def _trace(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def argon4_decide(topic="quantumdots-demo"):
    """Gemini Argon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-argon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Argon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all device and product gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="quantumdots-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Say it in the first line of every report: these are textbook models with labelled parameters - then show the 1/L^2 spacing law, the E_C/kT ratio, and the Brus wavelength next to the bulk value it shifted from.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["a hard-walled box shrinking while its level ladder spreads apart",
                  "harmonic shells filling two, six, twelve electrons at a time",
                  "a gate-voltage axis with diamond windows where N cannot change",
                  "dots shrinking across the frame as their glow shifts red to blue",
                  "a singlet and a triplet splitting apart by twice the exchange integral"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": argon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    # 1. particle in a box - the 1/L^2 law
    chk("box_ground_scales_inverse_L2",
        abs(box_energy_1d_ev(1, 5.0) / box_energy_1d_ev(1, 10.0) - 4.0) < 1e-9)
    chk("box_levels_n_squared",
        abs(box_energy_1d_ev(3, 10.0) / box_energy_1d_ev(1, 10.0) - 9.0) < 1e-9)
    chk("box_spacing_grows_as_dot_shrinks",
        box_spacing_1d_ev(1, 5.0) > box_spacing_1d_ev(1, 10.0)
        > box_spacing_1d_ev(1, 20.0) > box_spacing_1d_ev(1, 40.0))
    chk("box_spacing_ratio_exact_4x",
        abs(box_spacing_1d_ev(1, 10.0) / box_spacing_1d_ev(1, 20.0) - 4.0)
        < 1e-9)
    chk("box_spacing_odd_multiples",
        abs(box_spacing_1d_ev(2, 10.0) / box_spacing_1d_ev(1, 10.0) - 5.0 / 3.0)
        < 1e-9)
    chk("box_heavier_mass_lower_energy",
        box_energy_1d_ev(1, 10.0, m_eff=0.2)
        < box_energy_1d_ev(1, 10.0, m_eff=GAAS_M_EFF))
    chk("box_gaas_10nm_ground_class",
        0.050 < box_energy_1d_ev(1, 10.0) < 0.062)
    levels3d = box_levels_3d_ev(10.0)
    chk("box_3d_ground_triple_degeneracy_free",
        levels3d[0][1] == 1 and levels3d[0][2] == [(1, 1, 1)])
    chk("box_3d_first_excited_degeneracy_3",
        levels3d[1][1] == 3
        and abs(levels3d[1][0] / levels3d[0][0] - 2.0) < 1e-9)
    chk("box_3d_second_excited_degeneracy_3",
        levels3d[2][1] == 3
        and abs(levels3d[2][0] / levels3d[0][0] - 3.0) < 1e-9)
    chk("box_3d_222_is_4x_ground",
        any(abs(e / levels3d[0][0] - 4.0) < 1e-9 and d == 1
            for e, d, _ in levels3d))

    # 2. harmonic shells + magic numbers
    shells2 = harmonic_shells_2d()
    chk("shells_2d_magic_numbers",
        [r["cumulative_electrons"] for r in shells2] == [2, 6, 12, 20])
    chk("shells_2d_energies_linear",
        [r["energy_mev"] for r in shells2] == [3.0, 6.0, 9.0, 12.0])
    chk("shells_2d_capacities",
        [r["spin_capacity"] for r in shells2] == [2, 4, 6, 8])
    shells3 = harmonic_shells_3d()
    chk("shells_3d_magic_numbers",
        [r["cumulative_electrons"] for r in shells3] == [2, 8, 20, 40])
    chk("shells_3d_ground_energy",
        abs(shells3[0]["energy_mev"] - 1.5 * HW_MEV) < 1e-12)
    ladder = single_particle_levels_mev(count=12)
    chk("level_ladder_first_12",
        ladder == [3.0, 3.0, 6.0, 6.0, 6.0, 6.0,
                   9.0, 9.0, 9.0, 9.0, 9.0, 9.0])

    # 3. constant interaction + Coulomb blockade
    ec = charging_energy_mev()
    chk("charging_energy_80aF_class", 1.95 < ec < 2.06)
    chk("charging_energy_inverse_C",
        abs(charging_energy_mev(40.0) / charging_energy_mev(80.0) - 2.0)
        < 1e-9)
    chk("thermal_energy_300K_class",
        25.0 < thermal_energy_mev(300.0) < 26.5)
    chk("mu_first_electron_is_level",
        abs(chemical_potential_mev(1) - HW_MEV) < 1e-9)
    chk("mu_second_electron_adds_ec",
        abs(chemical_potential_mev(2) - (HW_MEV + ec)) < 1e-9)
    chk("addition_within_shell_is_ec",
        abs(addition_energy_mev(1) - ec) < 1e-9
        and abs(addition_energy_mev(3) - ec) < 1e-9
        and abs(addition_energy_mev(4) - ec) < 1e-9)
    chk("addition_at_shell_closure_peaks",
        abs(addition_energy_mev(2) - (HW_MEV + ec)) < 1e-9
        and abs(addition_energy_mev(6) - (HW_MEV + ec)) < 1e-9)
    chk("addition_energy_always_positive",
        all(addition_energy_mev(n) > 0 for n in range(1, 12)))
    chk("total_energy_telescopes",
        abs(total_energy_mev(6)
            - sum(chemical_potential_mev(n) for n in range(1, 7))) < 1e-9)
    blk = blockade_report()
    rows = {r["temp_k"]: r for r in blk["rows"]}
    chk("blockade_ratio_dilution_fridge",
        rows[0.1]["ec_over_kt"] > 200.0 and rows[0.1]["blockaded"])
    chk("blockade_ratio_falls_with_T",
        rows[0.1]["ec_over_kt"] > rows[4.2]["ec_over_kt"]
        > rows[77.0]["ec_over_kt"] > rows[300.0]["ec_over_kt"])
    chk("no_blockade_at_room_temperature",
        rows[300.0]["ec_over_kt"] < 1.0 and not rows[300.0]["blockaded"])
    win = stability_windows()
    chk("stability_windows_tile_axis",
        all(abs(win[i]["v_high_mv"] - win[i + 1]["v_low_mv"]) < 1e-9
            for i in range(len(win) - 1)))
    chk("stability_window_widths_match_addition",
        all(abs(w["width_mev"] - addition_energy_mev(w["n_electrons"]))
            < 1e-9 for w in win if w["n_electrons"] >= 1))
    chk("stability_closure_window_widest",
        win[2]["width_mv"] > win[1]["width_mv"]
        and win[6]["width_mv"] > win[5]["width_mv"])

    # 4. Brus emission - smaller dot, bluer photon
    brus = brus_report()
    gaps = [r["gap_ev"] for r in brus["rows"]]
    waves = [r["wavelength_nm"] for r in brus["rows"]]
    chk("brus_gap_exceeds_bulk", all(g > CDSE_PARAMS["bulk_gap_ev"]
                                     for g in gaps))
    chk("brus_gap_monotonic_in_R",
        all(gaps[i] > gaps[i + 1] for i in range(len(gaps) - 1)))
    chk("brus_wavelength_monotonic_in_R",
        all(waves[i] < waves[i + 1] for i in range(len(waves) - 1)))
    chk("brus_emission_bluer_than_bulk",
        all(w < brus["bulk_wavelength_nm"] for w in waves))
    chk("brus_R2_gap_class", 2.45 < brus_gap_ev(2.0) < 2.65)
    chk("brus_R6_near_bulk", 1.75 < brus_gap_ev(6.0) < 1.85)
    chk("exciton_bohr_radius_cdse_class",
        5.0 < exciton_bohr_radius_nm() < 5.7)
    chk("brus_regime_labels",
        brus["rows"][0]["regime"] == "strong"
        and brus["rows"][-1]["regime"] == "weak")

    # 5. two-electron toy - exchange + CI
    st = two_electron_states()
    chk("exchange_splitting_is_2K",
        abs(st["singlet_triplet_splitting_mev"] - 2.0 * K01_MEV) < 1e-12)
    chk("triplet_below_open_singlet",
        st["open_triplet_01"] < st["open_singlet_01"])
    chk("closed_singlet_is_determinant_ground",
        st["closed_singlet_00"] < st["open_triplet_01"]
        < st["closed_singlet_11"])
    chk("closed_singlet_formula",
        abs(st["closed_singlet_00"] - (2.0 * HW_MEV + J00_MEV)) < 1e-12)
    ci = singlet_ci()
    chk("ci_ground_below_diagonal",
        ci["ground_energy_mev"] < singlet_ci_matrix()[0][0])
    chk("ci_lowering_small_and_positive",
        0.01 < ci["ci_lowering_mev"] < 0.10)
    chk("ci_ground_mostly_closed_shell",
        ci["ground_config_weights"][0] > 0.95)
    chk("ci_weights_normalised",
        abs(sum(ci["ground_config_weights"]) - 1.0) < 1e-5)
    vals, _ = _sorted_eig([[2.0, 1.0], [1.0, 2.0]])
    chk("jacobi_known_2x2",
        abs(vals[0] - 1.0) < 1e-10 and abs(vals[1] - 3.0) < 1e-10)
    mat3 = singlet_ci_matrix()
    vals3, vecs3 = _sorted_eig(mat3)
    chk("jacobi_reconstruction_3x3",
        all(abs(sum(vecs3[i][k] * vals3[k] * vecs3[j][k] for k in range(3))
                - mat3[i][j]) < 1e-9 for i in range(3) for j in range(3)))
    chk("jacobi_trace_preserved",
        abs(sum(vals3) - sum(mat3[i][i] for i in range(3))) < 1e-9)

    # 6. classifier - labels from the lab's own regime model
    chk("classifier_grid_size", len(TRAINING_GRID) == 432)
    rep = classifier_report()
    chk("classifier_shell_closure",
        rep["dilution_fridge_shell_closure_N2"] == "shell-filling")
    chk("classifier_mid_shell_blockaded",
        rep["dilution_fridge_mid_shell_N3"] == "coulomb-blockaded")
    chk("classifier_room_temp_open", rep["room_temperature_N4"] == "open")
    chk("classifier_helium_blockaded",
        rep["helium_bath_4K_mid_shell_N5"] == "coulomb-blockaded")
    chk("classifier_model_label_rules",
        model_label(0.5, 1.5, 2) == "open"
        and model_label(100.0, 1.5, 6) == "shell-filling"
        and model_label(100.0, 0.2, 3) == "coulomb-blockaded")
    chk("classifier_deterministic",
        classifier_report() == classifier_report())

    # 7. council seats + HOLD gates
    brains = brains_report()
    chk("argon4_no_override", brains["decider"]["can_override_hold"] is False
        and brains["decider"]["seat"]
        == "Gemini Argon 4 Extended Thinking")
    chk("claude_no_override", brains["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", brains["flow"]["rendered"] is False
        and brains["flow"]["live"] == 0)
    chk("hold_gate_count", len(HOLD_GATES) == 14)
    chk("all_actions_gated",
        all(gate(a) == "HOLD" for a in HOLD_GATES))
    chk("ungated_action_proceeds", gate("run_demo_simulation") == "PROCEED")
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("QuantumDots-Lab - quantum-dot confinement + charging lab")
    print("by Darion Kellar | MIT | pure stdlib | zero network | EDUCATION ONLY")
    print("=" * 68)
    print("\n[1] THE HONEST SCOPE - textbook models, labelled parameters")
    print("    Every number below comes from a textbook model (box, harmonic")
    print("    shells, constant interaction, Brus, Slater-Condon miniature)")
    print("    fed with LABELLED teaching parameters. Nothing is measured,")
    print("    no device exists, and no output is a device specification.")
    print("\n[2] Particle in a box - spacing explodes as the dot shrinks")
    for row in box_report():
        print(f"    L = {row['length_nm']:5.1f} nm | E1 {row['e1_mev']:8.2f} meV"
              f" | dE(1->2) {row['spacing_1_to_2_mev']:8.2f} meV"
              f" | dE(2->3) {row['spacing_2_to_3_mev']:8.2f} meV")
    print("    -> spacing scales as 1/L^2: halve L, quadruple the spacing.")
    print("\n[3] Harmonic shells - the artificial-atom periodic table")
    for row in harmonic_shells_2d():
        print(f"    2D shell {row['shell']} | E {row['energy_mev']:5.1f} meV"
              f" | holds {row['spin_capacity']} | cumulative "
              f"{row['cumulative_electrons']}")
    print("    -> 2D magic numbers 2, 6, 12, 20; 3D: "
          f"{[r['cumulative_electrons'] for r in harmonic_shells_3d()]}")
    blk = blockade_report()
    print(f"\n[4] Constant interaction - E_C = e^2/C = "
          f"{blk['charging_energy_mev']:.4f} meV (C = {DOT_CAPACITANCE_AF:.0f} aF,"
          " LABELLED)")
    for n in range(1, 9):
        print(f"    mu({n}) {chemical_potential_mev(n):6.3f} meV | "
              f"E_add({n}) {addition_energy_mev(n):6.3f} meV")
    print("    -> addition energy = E_C inside a shell, E_C + shell gap at")
    print("       closures (N = 2, 6): the sawtooth of Coulomb blockade.")
    for row in blk["rows"]:
        print(f"    T = {row['temp_k']:6.1f} K | kT {row['kt_mev']:9.5f} meV"
              f" | E_C/kT {row['ec_over_kt']:9.2f} | blockaded "
              f"{row['blockaded']}")
    print("\n[5] Stability windows - gate voltage ranges where N is frozen")
    for w in stability_windows(n_max=6):
        print(f"    N = {w['n_electrons']} | Vg {w['v_low_mv']:7.1f} .. "
              f"{w['v_high_mv']:7.1f} mV | width {w['width_mv']:5.1f} mV")
    brus = brus_report()
    print(f"\n[6] Brus emission (CdSe LABELLED) - exciton Bohr radius "
          f"{brus['exciton_bohr_radius_nm']:.2f} nm, bulk "
          f"{brus['bulk_wavelength_nm']:.1f} nm")
    for row in brus["rows"]:
        print(f"    R = {row['radius_nm']:.1f} nm | gap {row['gap_ev']:.4f} eV"
              f" | lambda {row['wavelength_nm']:6.1f} nm | "
              f"{row['regime']} confinement")
    print("    -> smaller dot, bigger gap, bluer photon. Brus limits: strong-")
    print("       confinement estimate; finite barriers + surface states ignored.")
    st = two_electron_states()
    ci = singlet_ci()
    print("\n[7] Two-electron toy - exchange splitting + CI mixing")
    print(f"    |00> singlet      {st['closed_singlet_00']:.3f} meV")
    print(f"    (0,1) triplet     {st['open_triplet_01']:.3f} meV")
    print(f"    (0,1) singlet     {st['open_singlet_01']:.3f} meV "
          f"(splitting 2K = {st['singlet_triplet_splitting_mev']:.2f} meV)")
    print(f"    CI ground singlet {ci['ground_energy_mev']:.4f} meV "
          f"(lowered {ci['ci_lowering_mev']:.4f} meV by mixing, "
          f"weights {ci['ground_config_weights']})")
    print("\n[8] Regime classifier (TinyML kNN, labels from the regime model)")
    for name, label in classifier_report().items():
        print(f"    {name:36s} -> {label}")
    print("\n[9] Advisory seats")
    brains = brains_report()
    print(f"    decider: {brains['decider']['decision']} "
          f"trace={brains['decider']['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {brains['advisor']['can_override_hold']}")
    print(f"    flow rendered = {brains['flow']['rendered']} "
          f"live = {brains['flow']['live']}")
    print(f"\n[10] HOLD gates: {len(HOLD_GATES)}")
    for key in HOLD_GATES:
        print(f"    HOLD  {key}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "box":
        print(json.dumps({"lengths": box_report(),
                          "levels_3d_10nm": [
                              {"energy_ev": e, "degeneracy": d,
                               "triples": t}
                              for e, d, t in box_levels_3d_ev(10.0)]},
                         indent=2, sort_keys=True))
        return 0
    if cmd == "shells":
        print(json.dumps({"shells_2d": harmonic_shells_2d(),
                          "shells_3d": harmonic_shells_3d(),
                          "ladder_12": single_particle_levels_mev(count=12)},
                         indent=2, sort_keys=True))
        return 0
    if cmd == "blockade":
        print(json.dumps({"blockade": blockade_report(),
                          "addition_energies_mev": {
                              str(n): addition_energy_mev(n)
                              for n in range(1, 13)},
                          "stability_windows": stability_windows()},
                         indent=2, sort_keys=True))
        return 0
    if cmd == "emission":
        print(json.dumps(brus_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "exchange":
        print(json.dumps({"states": two_electron_states(),
                          "ci_matrix": singlet_ci_matrix(),
                          "ci": singlet_ci()},
                         indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(classifier_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for key, value in HOLD_GATES.items():
            print(f"{key}: {value}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "fabrication_claim"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
