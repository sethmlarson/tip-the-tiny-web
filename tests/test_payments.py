from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import StatementError

import app


def test_new_payment_default_created_at(test_db_session):
    creator = app.Creator()
    payment_method = app.PaymentMethod()
    app.Payment()


def test_payment_timezone_awareness(test_db_session, test_payment_method):
    # Try a timezone unaware datetime and observe an error.
    payment = app.Payment(
        payment_amount=1,
        created_at=datetime.utcnow(),
        payment_method=test_payment_method,
    )
    test_db_session.add(payment)

    with pytest.raises(StatementError):
        test_db_session.commit()
    test_db_session.rollback()

    # Default value should be timezone aware.
    payment = app.Payment(
        payment_amount=1,
        payment_method=test_payment_method,
        created_at=None,
    )
    test_db_session.add(payment)
    test_db_session.commit()

    payment = test_db_session.query(app.Payment).first()
    assert payment.created_at is not None
    assert payment.created_at.tzinfo is not None

    test_db_session.delete(payment)
    test_db_session.commit()

    # Set a timezone aware value
    created_at = datetime.now(tz=UTC)
    payment = app.Payment(
        payment_amount=1,
        payment_method=test_payment_method,
        created_at=created_at,
    )
    test_db_session.add(payment)
    test_db_session.commit()

    payment = test_db_session.query(app.Payment).first()
    assert payment.created_at == created_at
    assert payment.created_at.tzinfo is not None
