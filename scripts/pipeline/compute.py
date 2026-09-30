"""Fiscal arithmetic. All variables in nominal terms, per cent or % of GDP."""

from .config import COUNTRY_NAMES


def compute_country(iso3, debt, r, real_growth, inflation, pb):
    """Derived metrics for one country.

    g          = real growth + inflation (nominal growth, approximately)
    pb*        = (r - g) / 100 * debt, the debt stabilising primary balance
    fiscal gap = pb - pb*, positive means the debt ratio is falling
    """
    g = real_growth + inflation
    pb_star = (r - g) / 100 * debt
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
