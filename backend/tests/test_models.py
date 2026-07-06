from datetime import date

from app.database import Base, engine, SessionLocal
from app.models import User, Goal


def test_create_user_and_goal():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    u = User(name="Manan", phone="+910000000000")
    db.add(u)
    db.commit()
    db.refresh(u)
    g = Goal(
        user_id=u.id,
        goal_type="retirement",
        goal_name="Retire",
        target_amount=20000000,
        target_date=date(2056, 1, 1),
        years=30,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    assert u.id and g.id and g.status == "active"
    db.close()
