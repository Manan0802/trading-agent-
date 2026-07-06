from app.services.advisor.tax_advisor import generate_tax_saving_plan


def test_full_80c_gap_for_high_earner():
    r = generate_tax_saving_plan(1500000, existing_80c=0)
    assert r["elss_recommended"] == 150000
    assert r["nps_recommended"] == 50000  # income > 5L, no nps
    assert r["health_insurance_gap"] == 25000


def test_existing_80c_reduces_recommendation():
    r = generate_tax_saving_plan(1500000, existing_80c=100000)
    assert r["elss_recommended"] == 50000


def test_has_nps_zeroes_nps():
    r = generate_tax_saving_plan(1500000, has_nps=True)
    assert r["nps_recommended"] == 0
