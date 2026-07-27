from app.services.marketdata.promoter import _parse

_SHELL = '''<div id="shareholding"><table><tbody><tr>
<td><button onclick="Company.showShareholders('promoters','quarterly',this)">
Promoters&nbsp;<span class="blue-icon">+</span></button></td>
{cells}
</tr><tr><td>FIIs</td><td>18.20%</td></tr></tbody></table></div>'''


def _html(*values: str) -> str:
    return _SHELL.format(cells="".join(f"<td>{v}%</td>" for v in values))


def test_the_last_four_quarters_are_returned_oldest_first():
    assert _parse(_html("50.27", "50.30", "50.31", "50.33", "50.24", "50.10")) == [
        50.31, 50.33, 50.24, 50.10,
    ]


def test_fewer_than_four_quarters_are_returned_as_they_are():
    assert _parse(_html("61.5", "60.0")) == [61.5, 60.0]


def test_a_promoterless_company_yields_an_empty_history_not_a_zero_signal():
    """Many of India's largest listed companies have no promoter. That is not
    a governance warning, so it must not look like one."""
    assert _parse('<div id="shareholding"><table><tr><td>FIIs</td><td>22%</td></tr></table></div>') == []


def test_a_page_without_the_section_yields_nothing():
    assert _parse("<html><body>Not found</body></html>") == []


def test_cells_from_the_next_row_are_not_swept_in():
    """The FII row that follows must not be read as more promoter quarters."""
    assert 18.20 not in _parse(_html("50.27", "50.30"))


def test_a_declining_stake_is_preserved_in_order():
    """Adani Enterprises really did go 73.97 to 71.97 across four quarters, and
    the direction is the whole signal."""
    values = _parse(_html("73.97", "74.67", "74.84", "71.97"))
    assert values[0] > values[-1]
