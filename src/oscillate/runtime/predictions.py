"""The prediction register. Single source of truth.

STATUS.md cites this module; the sweep header carries its sha256; the
predictions are never restated in prose. Restatement is how registers
drift.

P4 is registered in conditioned form: at T=360 the joining plateaus
(~25-50 ticks) sit below the survival threshold W+1=65, so the
transition band plausibly emits zero verified leaves. The
births-as-bursts fallback is the observable prediction if that holds.
"""

PREDICTIONS = {
    "P1_bracketing": "the rel_disc minimum band brackets the "
                     "r-transition band (where dr/dK is maximal)",
    "P2_gap_profile": "|gap| largest in the DRIFT band, smaller "
                      "through EDGE, ~0 at SUPER; sign positive in "
                      "DRIFT (rho_J >> rho_obs)",
    "P3_freeze_ac1": "observable-freeze runs contradicted by the "
                     "J-shadow coincide with high rho_obs-stream "
                     "lag-1 autocorrelation (test case: DRIFT)",
    "P4_verified_rate": "CONDITIONED pre-run: verified-leaf rate peaks "
                        "where episode length >= W+1. At T=360 the "
                        "joining plateaus (~25-50 ticks) sit below "
                        "W+1=65, so the transition band plausibly "
                        "emits zero leaves; births then carry the "
                        "signature as ~N discrete bursts, one per "
                        "joining event",
    "P5_fraction": "verification fraction ~1 in quasi-static bands; "
                   "-> 0 wherever episodes die sub-W (predicted: "
                   "the transition middle)",
    "P6_closure": "closure never fires while the roots staircase "
                  "is still stepping; closure during stepping = "
                  "false-exhaustion candidate for the W-probe",
    "P7_crosscheck": "per-root bins-crossed-per-tick (smoothed) from "
                     "the staircase vs tracker verified rate vs birth "
                     "rate: pairwise differences mean (i) estimator "
                     "bug, (ii) the survival filter (= P5), (iii) "
                     "multi-root reorganization coherence",
}

CONFIG = {
    "N": 12, "D": 8, "T": 360, "K": [0.2, 2.4],
    "degree": 6, "n_carrier": 2, "window": 64, "lag": 20,
    "fp_decimals": 3, "closure_threshold": 32, "seed": 7,
}
