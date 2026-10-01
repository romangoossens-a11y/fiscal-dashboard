"""Fiscal arithmetic. All variables in nominal terms, per cent or % of GDP."""

from .config import COUNTRY_NAMES


def stabilising_balance(r, g, debt):
    """Primary balance that keeps the debt ratio constant, % of GDP."""
    return (r - g) / (1 + g / 100) * debt / 100


def fiscal_gap(r, real_growth, inflation, pb, debt):
    return pb - stabilising_balance(r, real_growth + inflation, debt)


def compute_country(iso3, debt, r, real_growth, inflation, pb):
    """Derived metrics for one country.

    g          = real growth + inflation (nominal growth, approximately)
    pb*        = (r - g) / (1 + g) x debt, the debt stabilising primary
                 balance, exact form of d_t = d_(t-1) (1 + r) / (1 + g) - pb_t
                 with debt at the end of the previous year
    fiscal gap = pb - pb*, positive means the debt ratio is falling
    """
    g = real_growth + inflation
    pb_star = stabilising_balance(r, g, debt)
    fiscal_gap = pb - pb_star
    return {
        "name": COUNTRY_NAMES[iso3],
        "iso3": iso3,
        "debt": round(debt, 1),
        "r": round(r, 2),
        "g": round(g, 2),
        "real_growth": round(real_growth, 2),
        "inflation": round(inflation, 2),
        "r_g": round(r - g, 2),
        "pb": round(pb, 2),
        "pb_star": round(pb_star, 2),
        "fiscal_gap": round(fiscal_gap, 2),
        "sustainable": fiscal_gap >= 0,
    }
