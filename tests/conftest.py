import pytest
from sqlalchemy.orm import Session

from app import BaseModel, Creator, GitHubSponsorsPaymentMethod, db_engine


@pytest.fixture(scope="function")
def test_db_session() -> Session:
    BaseModel.metadata.create_all(db_engine)
    try:
        with Session(bind=db_engine) as session:
            yield session
    finally:
        BaseModel.metadata.drop_all(db_engine)


@pytest.fixture(scope="function")
def test_creator(test_db_session):
    creator = Creator(
        slug="python-software-foundation",
        display_name="Python Software Foundation",
        web_url="https://python.org/psf-landing",
    )
    test_db_session.add(creator)
    test_db_session.commit()
    yield creator


@pytest.fixture(scope="function")
def test_payment_method(test_db_session, test_creator):
    payment_method = GitHubSponsorsPaymentMethod(
        github_id=1525981,
        github_login="python",
        creator=test_creator,
    )
    test_db_session.add(payment_method)
    test_db_session.commit()
    yield payment_method
