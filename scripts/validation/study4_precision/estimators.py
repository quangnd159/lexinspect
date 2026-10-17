"""Study 4: design-based estimators and intervals (used by analyse.py).

Setting
-------
A finite population of hits is split into sub-strata h of size N_h. Within h
a simple random sample without replacement is drawn. A domain d is a union of
whole sub-strata (module, category, dimension, K-band, multi-sense flag) or
cuts across them (register). M_hd, the domain's population in h, comes from
the sampling frame (exact) or, without one, is estimated (then no limit
below is exact, and the output says so). A cell is (h, d) with M_hd > 0.

Assumption for the point estimate and the primary limits: given the resolved
domain counts, the resolved units of each cell are a uniform random subset of
the cell, independently across sub-strata ("resolution exchangeable with
correctness" in this strong sense; equal response rates alone do not ensure
it). Resolution-adjusted point estimate: each resolved item of h gets the
weight N_h / r_h,
    P_d = sum_{i in d} w_i y_i / sum_{i in d} w_i.
A cell with population but no resolved domain item has no observed mean, so P_d
is then NOT reported for the domain (`p` = None, `p_scope` =
"represented_cells_only"); the ratio over the represented cells is given as
`p_represented`, labelled as such. No imputation is made.

Inputs are checked, never repaired: cells must satisfy
0 <= k_lo <= k_hi <= a <= M (integers), and an exact (frame) cell population
below the number of sampled domain items is an error. Estimated cell
populations (no frame) make the limits non-exact, and this is flagged.

PRIMARY: exact, pointwise, finite-population 95% limits from a joint
stratified tail bound (`exact_limits`)
---------------------------------------------------------------------
Under that assumption the number correct X_hd among the a_hd resolved domain
items of a cell is hypergeometric(M_hd, T_hd, a_hd), independently across
cells. The target is P_d = sum T_hd / M_d.
- Census cells (a_hd = M_hd) are known exactly; cells with no resolved domain
  item (a_hd = 0) are wholly unknown: they add 0 to the lower and M_hd to the
  upper count limit (their mass is never dropped). No error is spent on
  either.
- One remaining cell: the exact hypergeometric (Clopper-Pearson-type) limits,
  each side at a/2.
- Two or more remaining cells: an exact limit from one joint tail bound over
  the domain's cells (no Bonferroni split across cells).
  For the statistic S = sum_h w_h X_h / a_h (w_h = M_hd / M over the
  remaining cells) and any lambda > 0, mu > 0,
      sup_{T: sum w T/M = P0} P(S >= s) <= exp(-lambda s + mu P0 + sum_h phi_h)
      phi_h = max over T_h in 0..M_hd of
              [log E exp(lambda w_h X_h / a_h) - mu w_h T_h / M_hd]
  (Chernoff bound, then weak Lagrangian duality for the nuisance T). The log
  moment generating function is the exact hypergeometric one for cells with
  M_hd <= FPC_EXACT_MAX_M and sampling fraction a_hd / M_hd >=
  FPC_EXACT_MIN_FRACTION (where the finite-population correction matters),
  and Hoeffding's (1963, Theorem 4) binomial upper bound otherwise (valid for
  every cell; it ignores the correction), maximised over p_h in closed form. Every P0 with
  that bound <= a/2 is rejected; the lower limit is
      L = sup_{lambda, mu > 0} (log(a/2) + lambda s - sum_h phi_h) / mu,
  maximised over a refined grid. Every grid point gives a valid limit, so an
  imperfect maximisation can only widen the interval. The upper limit is the
  same construction applied to 1 - y.
Which construction applies depends only on M_hd and the resolved counts a_hd,
never on the observed outcomes. For one domain, coverage is at least 1 - a for
every configuration of the T_hd, given the frame and the assumption above. The
statement is POINTWISE: each reported interval spends a/2 per tail on its own;
nothing is claimed simultaneously across domains, constructions or modules.

CO-PRIMARY: exact resolution region (`exact_limits` on bounding outcomes)
-------------------------------------------------------------------------
No assumption about why items are unresolved. Over all sampled domain items
(resolved or not), the lower end counts only resolved-correct items as 1 and
the upper end counts only resolved-incorrect items as 0; the population
versions bracket P_d. The lower end gets the exact lower limit (a/2) of the
first, the upper end the exact upper limit (a/2) of the second, so the region
covers P_d with probability at least 1 - a whatever the resolution mechanism
(given the frame).

SECONDARY, the only approximate interval: Korn-Graubard modified Wilson
------------------------------------------------------
Taylor-linearised variance of the ratio with the finite-population correction,
    z_i = I_d(i)(y_i - P_d) / N^_d,  Var = sum_h N_h^2 (1 - r_h/N_h) s^2_{z,h} / r_h,
and the modified Wilson interval documented for SAS PROC SURVEYFREQ
(SAS/STAT 13.1 User's Guide, The SURVEYFREQ Procedure, "Confidence Limits
for Proportions" and "Degrees of Freedom"; Korn & Graubard 1998):
    n_e = P(1 - P) / Var,  n_e* = n_e (t_{n_d - 1} / t_df)^2 truncated at n_d,
    Wilson limits at n_e* with kappa = z_{1 - a/2},
n_d = resolved domain items, df = resolved sampled items of the module and
outcome minus the sub-strata holding them (a fixed convention). Reported only
when 0 < P < 1, Var > 0, n_d >= 2 and df >= 1; otherwise not reported (see the
exact limits). Single-item sub-strata contribute no variance and are flagged.
If positive-population cells have no resolved domain item the interval refers
to the represented cells only (`ci95_approx_scope`), not to the domain. Its
coverage is approximate: simulation shows undercoverage near the boundary and
for register domains, so it supports no confirmatory claim.

Descriptive endpoints (not confidence limits): unresolved sampled items
counted wrong / right with weights M_hd / (sampled domain items in h), cells
with no sampled domain item counted 0 / 1.

References: Korn, E. L., & Graubard, B. I. (1998). Survey Methodology, 24(2),
193-201. Hoeffding, W. (1963). Probability inequalities for sums of bounded
random variables. JASA, 58(301), 13-30. SAS Institute, SAS/STAT 13.1 User's
Guide, The SURVEYFREQ Procedure. Wilson, E. B. (1927). JASA, 22(158), 209-212.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np

ALPHA = 0.05
FPC_EXACT_MAX_M = 2500  # exact hypergeometric MGF for cells up to this size ...
FPC_EXACT_MIN_FRACTION = 0.05  # ... and with sampling fraction a/M at least this
_GRID = 31
_ROUNDS = 7


# --- quantiles -------------------------------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularised incomplete beta (Lentz's method)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        for aa in (
            m * (b - m) * x / ((qam + m2) * (a + m2)),
            -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2)),
        ):
            d = 1 + aa * d
            d = 1 / (d if abs(d) > tiny else tiny)
            c = 1 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1) < 3e-14:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    )
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1 - math.exp(lbt) * _betacf(b, a, 1 - x) / b


def norm_ppf(p: float) -> float:
    """Standard normal quantile (bisection on erfc)."""
    lo, hi = -40.0, 40.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if 0.5 * math.erfc(-mid / math.sqrt(2)) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def t_ppf(p: float, df: float) -> float:
    """Student t quantile for p > 0.5 (bisection on the exact CDF); normal if df is infinite."""
    if not math.isfinite(df) or df > 1e7:
        return norm_ppf(p)
    tail = 1 - p
    lo, hi = 0.0, 1e6
    for _ in range(300):
        mid = (lo + hi) / 2
        if 0.5 * betainc(df / 2, 0.5, df / (df + mid * mid)) > tail:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def wilson(p: float, n: float, z: float | None = None, alpha: float = ALPHA):
    """Wilson score interval; `n` may be an effective (non-integer) size."""
    if p is None or n is None or n <= 0:
        return None
    z = norm_ppf(1 - alpha / 2) if z is None else z
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(max(0.0, p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


# --- hypergeometric ----------------------------------------------------------------


def _lcomb(n: int, k: int) -> float:
    if k < 0 or k > n:
        return -math.inf
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def _pmf(x: int, M: int, T: int, n: int) -> float:
    lp = _lcomb(T, x) + _lcomb(M - T, n - x) - _lcomb(M, n)
    return 0.0 if lp == -math.inf else math.exp(lp)


def hyper_cdf(k: int, M: int, T: int, n: int) -> float:
    """P(X <= k) for X ~ Hypergeometric(population M, successes T, draws n)."""
    return min(1.0, sum(_pmf(x, M, T, n) for x in range(0, k + 1)))


def hyper_sf(k: int, M: int, T: int, n: int) -> float:
    """P(X >= k)."""
    return min(1.0, sum(_pmf(x, M, T, n) for x in range(k, n + 1)))


def hyper_lcl(k: int, n: int, M: int, alpha1: float) -> int:
    """Exact one-sided lower limit for T: the smallest T with P(X >= k | T) > alpha1."""
    if n >= M:
        return k
    if k == 0:
        return 0
    a, b = k, M - (n - k)
    while a < b:
        mid = (a + b) // 2
        if hyper_sf(k, M, mid, n) > alpha1:
            b = mid
        else:
            a = mid + 1
    return a


def hyper_ucl(k: int, n: int, M: int, alpha1: float) -> int:
    """Exact one-sided upper limit for T: the largest T with P(X <= k | T) > alpha1."""
    if n >= M:
        return k
    if k == n:
        return M
    a, b = k, M - (n - k)
    while a < b:
        mid = (a + b + 1) // 2
        if hyper_cdf(k, M, mid, n) > alpha1:
            a = mid
        else:
            b = mid - 1
    return a


def hyper_count_ci(k: int, n: int, M: int, alpha: float) -> tuple[int, int]:
    """Exact two-sided limits for the population count T, given k of n drawn from M."""
    return hyper_lcl(k, n, M, alpha / 2), hyper_ucl(k, n, M, alpha / 2)


def bonferroni_hypergeometric(
    cells: list[tuple[int, int, int]], alpha: float
) -> tuple[float, float]:
    """Alternative exact limits (not used for inference): per-cell hypergeometric limits at
    a / C, C = cells with 0 < a < M, summed. Valid but far wider than the joint limit when
    there are many cells; kept for comparison."""
    uncertain = [c for c in cells if 0 < c[1] < c[0]]
    a_cell = alpha / max(1, len(uncertain))
    lo = hi = 0.0
    total = sum(m for m, _, _ in cells)
    for m, a, k in cells:
        if a == 0:
            hi += m
        elif a >= m:
            lo += k
            hi += k
        else:
            t_lo, t_hi = hyper_count_ci(k, a, m, a_cell)
            lo += t_lo
            hi += t_hi
    return lo / total, hi / total


# --- exact joint limits ------------------------------------------------------------


@lru_cache(maxsize=8192)
def _log_fact(m: int) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(np.log(np.arange(1, m + 1, dtype=float)))])


@lru_cache(maxsize=4096)
def _logpmf_matrix(M: int, n: int) -> np.ndarray:
    """log P(X = x | T) for T = 0..M (rows), x = 0..n (columns); -inf where impossible."""
    lf = _log_fact(M)
    T = np.arange(M + 1)[:, None]
    x = np.arange(n + 1)[None, :]
    ok = (x <= T) & (n - x <= M - T)
    Tc = np.where(ok, T, 0)
    xc = np.where(ok, x, 0)
    a = lf[Tc] - lf[xc] - lf[np.maximum(Tc - xc, 0)]
    b = lf[M - Tc] - lf[n - xc] - lf[np.maximum(M - Tc - n + xc, 0)]
    out = a + b - (lf[M] - lf[n] - lf[M - n])
    return np.where(ok, out, -np.inf)


@lru_cache(maxsize=4096)
def _pmf_matrix(M: int, n: int) -> np.ndarray:
    return np.exp(_logpmf_matrix(M, n))


def _hyper_lmgf(M: int, n: int, c: np.ndarray) -> np.ndarray:
    """log E exp(c X), X ~ Hypergeometric(M, T, n), for each c (rows) and T = 0..M (columns).

    A matrix product on exp(c (x - n)) <= 1; entries that underflow are recomputed in log
    space. A slack of 1e-9 is added so rounding can only enlarge the bound.
    """
    x = np.arange(n + 1, dtype=float)
    v = np.exp(c[None, :] * (x[:, None] - n))  # (n+1, G)
    r = _pmf_matrix(M, n) @ v  # (M+1, G)
    bad = r < 1e-250
    out = np.log(np.where(bad, 1.0, r)) + c[None, :] * n
    if bad.any():
        lp = _logpmf_matrix(M, n)
        ti, gi = np.nonzero(bad)
        z = lp[ti, :] + c[gi][:, None] * x[None, :]
        zmax = z.max(axis=1)
        out[ti, gi] = zmax + np.log(np.exp(z - zmax[:, None]).sum(axis=1))
    return (out + 1e-9).T


def _phi(lams: np.ndarray, mus: np.ndarray, cells: list[tuple[float, int, int]]) -> np.ndarray:
    """sum_h phi_h(lambda, mu) on the grid lams x mus; cells (w_h, a_h, M_h)."""
    total = np.zeros((len(lams), len(mus)))
    for w, n, big_m in cells:
        c = lams * w / n  # (G,)
        if big_m <= FPC_EXACT_MAX_M and n / big_m >= FPC_EXACT_MIN_FRACTION:
            lmgf = _hyper_lmgf(big_m, n, c)  # (G, M+1)
            pen = (w / big_m) * np.arange(big_m + 1)  # (M+1,)
            total += (lmgf[:, None, :] - mus[None, :, None] * pen[None, None, :]).max(axis=2)
        else:
            # Binomial MGF (Hoeffding 1963, Thm 4), maximised over p in [0, 1] in closed form.
            cc = c[:, None]
            mm = mus[None, :]
            em1 = np.expm1(np.minimum(cc, 700.0))
            with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
                p = np.clip(n / (mm * w) - 1.0 / em1, 0.0, 1.0)
                lt = np.logaddexp(
                    np.log(np.maximum(1 - p, 1e-300)), np.log(np.maximum(p, 1e-300)) + cc
                )
            lt = np.where(p <= 0, 0.0, np.where(p >= 1, cc + 0 * p, lt))
            total += n * lt - mm * w * p
    return total


def _lower_joint(s: float, cells: list[tuple[float, int, int]], alpha1: float) -> float:
    """Exact lower limit for sum w_h p_h given S = s (see the module docstring)."""
    if s <= 0:
        return 0.0
    la = math.log(alpha1)
    best = 0.0
    lc, mc, span = 2.0, 2.0, 4.0  # log10 centre of lambda and mu, half-width
    for it in range(_ROUNDS):
        lams = 10 ** np.linspace(lc - span, lc + span, _GRID)
        mus = 10 ** np.linspace(mc - span, mc + span, _GRID)
        v = (la + lams[:, None] * s - _phi(lams, mus, cells)) / mus[None, :]
        i, j = np.unravel_index(int(np.argmax(v)), v.shape)
        if v[i, j] > best:
            best = float(v[i, j])
            lc, mc = math.log10(lams[i]), math.log10(mus[j])
        span = 1.5 if it == 0 else span / 2.5
    return max(0.0, min(best, s))


def exact_limits(
    cells: list[tuple[int, int, int, int]],
    alpha_lo: float | None,
    alpha_hi: float | None,
) -> dict[str, Any]:
    """Exact limits for sum_h T_h / sum_h M_h.

    cells: (M_h, a_h, k_lo_h, k_hi_h); the lower limit uses k_lo (one-sided level
    alpha_lo), the upper k_hi (alpha_hi); None skips a side. For a plain interval
    k_lo = k_hi. Returns lower, upper (proportions), method, unobserved_share.
    """
    for c in cells:
        if len(c) != 4 or any(isinstance(v, bool) or v != int(v) for v in c):
            raise ValueError(f"cell {c!r}: need four integers (M, a, k_lo, k_hi)")
        m, a, kl, kh = (int(v) for v in c)
        if not (0 <= kl <= kh <= a <= m):
            raise ValueError(f"cell {c!r}: need 0 <= k_lo <= k_hi <= a <= M")
    cells = [(int(m), int(a), int(kl), int(kh)) for m, a, kl, kh in cells if m > 0]
    total = sum(m for m, *_ in cells)
    if total == 0:
        return {"lower": None, "upper": None, "method": None, "unobserved_share": None}
    fixed_lo = sum(kl for m, a, kl, _ in cells if a >= m)
    fixed_hi = sum(kh for m, a, _, kh in cells if a >= m)
    unobs = sum(m for m, a, _, _ in cells if a == 0)
    samp = [c for c in cells if 0 < c[1] < c[0]]
    lo = hi = None
    if not samp:
        method = "census" if unobs == 0 else "census_and_unobserved"
        lo, hi = fixed_lo, fixed_hi + unobs
    elif len(samp) == 1:
        method = "exact_hypergeometric"
        m, a, kl, kh = samp[0]
        if alpha_lo is not None:
            lo = fixed_lo + hyper_lcl(kl, a, m, alpha_lo)
        if alpha_hi is not None:
            hi = fixed_hi + unobs + hyper_ucl(kh, a, m, alpha_hi)
    else:
        method = "exact_stratified_chernoff"
        ms = sum(m for m, *_ in samp)
        jc = [(m / ms, a, m) for m, a, _, _ in samp]
        if alpha_lo is not None:
            s_lo = sum(m / ms * kl / a for m, a, kl, _ in samp)
            lo = fixed_lo + _lower_joint(s_lo, jc, alpha_lo) * ms
        if alpha_hi is not None:
            s_hi = sum(m / ms * (a - kh) / a for m, a, _, kh in samp)
            hi = fixed_hi + unobs + (1 - _lower_joint(s_hi, jc, alpha_hi)) * ms
    return {
        "lower": None if lo is None else lo / total,
        "upper": None if hi is None else min(1.0, hi / total),
        "method": method,
        "unobserved_share": unobs / total,
    }


# --- domain estimator --------------------------------------------------------------


@dataclass
class Stratum:
    """One sub-stratum, seen from one domain and one outcome."""

    name: str
    N: int  # population of the sub-stratum
    M: float  # domain population in the sub-stratum (exact if M_exact)
    M_exact: bool
    resolved: list[tuple[bool, int]] = field(default_factory=list)  # (in domain, y)
    domain_sampled: list[int | None] = field(default_factory=list)  # y (None: unresolved)


def design_df(strata: list[Stratum]) -> float:
    """Pre-specified convention: resolved sampled items minus sub-strata holding any."""
    r = sum(len(s.resolved) for s in strata)
    h = sum(1 for s in strata if s.resolved)
    return float(r - h)


def _clean_df(df: float) -> tuple[float | None, str]:
    if df is None or (isinstance(df, float) and math.isnan(df)):
        return None, "undefined"
    if not math.isfinite(df):
        return None, "infinite"
    if df < 1:
        return df, "too_small"
    return df, "finite"


def _cell_m(s: Stratum) -> int:
    """The cell population used by the exact limits. Exact populations are checked, never
    repaired; an estimated population (no frame) is rounded up to the sampled count and the
    result is flagged as not exact by the caller."""
    dom_n = len(s.domain_sampled)
    if s.M_exact:
        if s.M < 0 or int(s.M) != s.M:
            raise ValueError(f"{s.name}: domain population {s.M!r} is not a nonnegative integer")
        if int(s.M) < dom_n:
            raise ValueError(
                f"{s.name}: frame domain population {int(s.M)} is below the {dom_n} sampled "
                "domain items"
            )
        if int(s.M) > s.N:
            raise ValueError(f"{s.name}: domain population {int(s.M)} exceeds N_h = {s.N}")
        return int(s.M)
    return max(int(math.ceil(s.M - 1e-9)), dom_n) if s.M > 0 else 0


def domain_estimate(strata: list[Stratum], df: float, alpha: float = ALPHA) -> dict[str, Any]:
    """Point estimate, exact limits, exact resolution region and the approximate interval."""
    warnings: list[str] = []
    big_m = sum(s.M for s in strata)
    exact_pop = all(s.M_exact for s in strata if s.M > 0)
    df_val, df_status = _clean_df(df)
    n_items = sum(len(s.domain_sampled) for s in strata)
    out: dict[str, Any] = {
        "p": None,
        "p_represented": None,
        "p_scope": None,
        "ci95_exact": None,
        "ci95_exact_method": None,
        "region95_exact": None,
        "region95_exact_method": None,
        "ci95_approx": None,
        "ci95_approx_method": None,
        "ci95_approx_scope": None,
        "ci95_approx_status": None,
        "se": None,
        "var": None,
        "n_eff": None,
        "df": df_val,
        "df_status": df_status,
        "N_hat": None,
        "population": big_m,
        "population_exact": exact_pop,
        "n_items": n_items,
        "n_resolved": 0,
        "resolution_rate": None,
        "represented_share": None,
        "unobserved_share_exact": None,
        "bounds_unresolved_wrong_right": None,
        "singleton_strata": [],
        "census_strata": [],
        "homogeneous_share": None,
        "unweighted": None,
        "warnings": warnings,
    }
    if big_m <= 0:
        return out
    if not exact_pop:
        warnings.append(
            "domain population per sub-stratum estimated (no frame counts): "
            "the limits are not exact (they use estimated domain populations)"
        )
    # Exact limits (primary) and the resolution region (co-primary).
    cells_p, cells_r = [], []
    for s in strata:
        m = _cell_m(s)
        if m <= 0:
            continue
        dom = [y for ind, y in s.resolved if ind]
        k = sum(dom)
        cells_p.append((m, len(dom), k, k))
        ys = s.domain_sampled
        cells_r.append(
            (m, len(ys), sum(1 for y in ys if y == 1), len(ys) - sum(1 for y in ys if y == 0))
        )
    ex = exact_limits(cells_p, alpha / 2, alpha / 2)
    rg = exact_limits(cells_r, alpha / 2, alpha / 2)
    out["ci95_exact"] = (ex["lower"], ex["upper"])
    out["ci95_exact_method"] = ex["method"]
    out["unobserved_share_exact"] = ex["unobserved_share"]
    out["region95_exact"] = (rg["lower"], rg["upper"])
    out["region95_exact_method"] = rg["method"]
    # Descriptive endpoints.
    lo = hi = 0.0
    for s in strata:
        if s.M <= 0:
            continue
        if s.domain_sampled:
            w = s.M / len(s.domain_sampled)
            lo += w * sum(y or 0 for y in s.domain_sampled)
            hi += w * sum(1 if y is None else y for y in s.domain_sampled)
        else:
            hi += s.M
    out["bounds_unresolved_wrong_right"] = (lo / big_m, hi / big_m)
    represented = sum(s.M for s in strata if s.M > 0 and any(ind for ind, _ in s.resolved))
    out["represented_share"] = represented / big_m
    if represented < big_m:
        warnings.append(
            f"{1 - represented / big_m:.1%} of the domain population is in sub-strata with no "
            "resolved domain item: unknown in the exact limits, outside the approximate interval"
        )
    num = den = 0.0
    n_d = k_d = 0
    for s in strata:
        r = len(s.resolved)
        if r == 0:
            continue
        w = s.N / r
        for ind, y in s.resolved:
            if ind:
                num += w * y
                den += w
                n_d += 1
                k_d += y
    out["n_resolved"] = n_d
    out["resolution_rate"] = n_d / n_items if n_items else None
    if n_d == 0:
        warnings.append("no resolved item in the domain: no point estimate")
        out["ci95_approx_status"] = "no resolved item"
        return out
    p = num / den
    var = 0.0
    hom_w = 0.0
    for s in strata:
        r = len(s.resolved)
        dom = [y for ind, y in s.resolved if ind]
        if r == 0 or not dom:
            continue
        if r >= s.N:
            out["census_strata"].append(s.name)
            continue
        if r == 1:
            out["singleton_strata"].append(s.name)
            continue
        if len(dom) >= 2 and len(set(dom)) == 1:
            hom_w += s.N / r * len(dom)
        z = [(y - p) / den if ind else 0.0 for ind, y in s.resolved]
        mz = sum(z) / r
        s2 = sum((x - mz) ** 2 for x in z) / (r - 1)
        var += s.N * s.N * (1 - r / s.N) * s2 / r
    scope = "domain" if represented >= big_m else "represented_cells_only"
    out |= {
        "p": p if scope == "domain" else None,
        "p_represented": p,
        "p_scope": scope,
        "var": var,
        "se": math.sqrt(var),
        "N_hat": den,
        "homogeneous_share": hom_w / den,
        "unweighted": {
            "p": k_d / n_d,
            "ci95": wilson(k_d / n_d, n_d, alpha=alpha),
            "n": n_d,
            "k": k_d,
        },
    }
    if out["singleton_strata"]:
        warnings.append(
            f"{len(out['singleton_strata'])} non-census sub-strata with a single resolved "
            "domain item: no variance contribution in the approximate interval"
        )
    out["ci95_approx_scope"] = scope
    if scope != "domain":
        warnings.append(
            "no domain point estimate: some cells with population have no resolved item "
            "(p_represented covers the represented cells only)"
        )
    census_only = all(len(s.resolved) >= s.N for s in strata if s.M > 0)
    if census_only and var == 0:
        out["ci95_approx"], out["ci95_approx_method"] = (p, p), "census"
        out["ci95_approx_status"] = "census"
        return out
    if not (0 < p < 1 and var > 0 and n_d >= 2 and df_status == "finite"):
        out["ci95_approx_status"] = (
            "not reported: boundary estimate, zero variance, n_d < 2 or df < 1 "
            "(use the exact limits)"
        )
        return out
    z = norm_ppf(1 - alpha / 2)
    n_e = p * (1 - p) / var
    adj = (t_ppf(1 - alpha / 2, n_d - 1) / t_ppf(1 - alpha / 2, df_val)) ** 2
    n_star = min(n_e * adj, float(n_d))
    out["n_eff"] = n_star
    out["ci95_approx"] = wilson(p, n_star, z)
    out["ci95_approx_method"] = "korn_graubard_modified_wilson"
    out["ci95_approx_status"] = "approximate"
    return out
