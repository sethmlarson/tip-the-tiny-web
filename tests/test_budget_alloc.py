import pytest

import app
from app import BudgetAllocation


def support_n_creators(
    *, number_of_creators: int, db, supporter: app.Supporter, want_to_pay: bool = True
) -> list[app.Creator]:
    """Helper function which creates a number of creators for a supporter."""
    creators = []
    for n in range(number_of_creators):
        creator = app.Creator(
            display_name=f"Creator {n}",
            slug=f"creator-{n}",
            web_url=f"https://example{n}.com",
        )
        supporter_to_creator = app.SupporterToCreator(
            creator=creator,
            supporter=supporter,
            want_to_pay=want_to_pay,
        )
        db.add(creator)
        db.add(supporter_to_creator)
        creators.append(creator)
    db.commit()
    return creators


def test_no_creators(test_db_session):
    supporter = app.Supporter()
    supporter.budget_per_month = 1000
    test_db_session.add(supporter)
    test_db_session.commit()

    budget_alloc = app.calculate_next_budget_alloc(supporter)
    assert budget_alloc is None


def test_not_paying_creators(test_db_session):
    supporter = app.Supporter()
    supporter.budget_per_month = 1000
    test_db_session.add(supporter)
    test_db_session.commit()

    support_n_creators(
        number_of_creators=5, db=test_db_session, supporter=supporter, want_to_pay=False
    )

    budget_alloc = app.calculate_next_budget_alloc(supporter)
    assert budget_alloc is None


@pytest.mark.parametrize("number_of_creators", [1, 5, 999, 1000])
def test_distribute_to_creators(test_db_session, number_of_creators):
    supporter = app.Supporter()
    supporter.budget_per_month = 1000
    test_db_session.add(supporter)
    test_db_session.commit()

    support_n_creators(
        number_of_creators=number_of_creators, db=test_db_session, supporter=supporter
    )

    budget_alloc = app.calculate_next_budget_alloc(supporter)
    assert budget_alloc is not None
    assert budget_alloc.allocation_amount == 1000
    assert budget_alloc.supporter_id == supporter.id

    app.distribute_budget_alloc(supporter, budget_alloc)
    supports = (
        test_db_session.query(app.SupporterToCreator)
        .where(app.SupporterToCreator.supporter_id == supporter.id)
        .all()
    )
    budget_per_creator = 1000 // number_of_creators
    assert len(supports) == number_of_creators
    print([support.payment_amount_outstanding for support in supports])
    assert all(
        support.payment_amount_outstanding == budget_per_creator for support in supports
    )

    budget_alloc = test_db_session.query(BudgetAllocation).first()
    assert budget_alloc is not None
    assert budget_alloc.allocation_amount == (budget_per_creator * number_of_creators)
