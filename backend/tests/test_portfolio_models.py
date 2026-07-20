from datetime import date

from app.database import Base, SessionLocal, engine
from app.models import Holding, Transaction, User


def test_create_holding_with_transactions():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    u = User(
        name="Investor",
        phone="+910000000009",
        email="investor@example.com",
        hashed_password="x",
    )
    db.add(u)
    db.commit()
    db.refresh(u)

    h = Holding(
        user_id=u.id,
        name="Parag Parikh Flexi Cap Fund - Direct Growth",
        asset_type="MF",
        identifier="122639",
        category="Flexi Cap",
    )
    db.add(h)
    db.commit()
    db.refresh(h)

    # Two SIP instalments — irregular dates are fine, each buy is its own row.
    db.add_all(
        [
            Transaction(
                holding_id=h.id,
                txn_date=date(2024, 1, 5),
                txn_type="BUY",
                units=100.0,
                price=50.0,
                amount=5000.0,
            ),
            Transaction(
                holding_id=h.id,
                txn_date=date(2024, 2, 5),
                txn_type="BUY",
                units=90.0,
                price=55.0,
                amount=4950.0,
            ),
        ]
    )
    db.commit()
    db.refresh(h)

    assert h.id and h.asset_type == "MF"
    assert len(h.transactions) == 2
    assert sum(t.units for t in h.transactions) == 190.0
    db.close()


def test_stock_holding_supported():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    u = User(
        name="Trader",
        phone="+910000000010",
        email="trader@example.com",
        hashed_password="x",
    )
    db.add(u)
    db.commit()
    db.refresh(u)

    h = Holding(
        user_id=u.id,
        name="Reliance Industries",
        asset_type="STOCK",
        identifier="RELIANCE.NS",
    )
    db.add(h)
    db.commit()
    db.refresh(h)

    assert h.asset_type == "STOCK" and h.category is None
    db.close()
