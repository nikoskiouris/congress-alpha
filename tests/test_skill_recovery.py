"""Recovery test: the DGP plants post-disclosure skill in Hale and none in Vale.

If this fails, the model is leaking trade-date information or not learning.
"""

from datetime import date

from congress_alpha.generate import generate
from congress_alpha.prices import PriceStore
from congress_alpha.skill import fit_skill


def test_recovers_post_disclosure_skill_not_pre_disclosure_illusion():
    uni = generate(seed=7, start=date(2021, 1, 4), end=date(2025, 12, 31))
    store = PriceStore(uni.prices)
    securities = {s.ticker: s for s in uni.securities}
    book = fit_skill(date(2025, 6, 1), uni.trades, securities, store, uni.politicians)
    # Avery Hale has real post-disclosure defense alpha.
    # Casey Vale only has pre-disclosure drift — tradable weight should be near 0 / below Hale.
    assert book.overall["hale"] > 0.2
    assert book.overall["hale"] > book.overall["vale"] + 0.15
    assert book.overall["vale"] < 0.25
    # Nash is an inverse trader.
    assert book.overall["nash"] < 0.0
    # Sector specialization: Hale's defense weight beats Hale's tech weight if both exist.
    def_w = book.sector.get(("hale", "Defense"))
    tech_w = book.sector.get(("hale", "Technology"), 0.0)
    assert def_w is not None
    assert def_w > tech_w
