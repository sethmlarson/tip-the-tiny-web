import os
import shutil
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app
from app import BaseModel, Creator, GitHubSponsorsPaymentMethod


@pytest.fixture(scope="function")
def test_db_session() -> Session:
    db_filepath = f"{tempfile.mkdtemp()}/app.sqlite"
    try:
        db_engine = create_engine(f"sqlite:///{db_filepath}")
        BaseModel.metadata.create_all(db_engine)
        prev_session = app.db
        try:
            with Session(bind=db_engine) as session:
                app.db = session
                yield session
        finally:
            app.db = prev_session
            BaseModel.metadata.drop_all(db_engine)

    finally:
        shutil.rmtree(os.path.dirname(db_filepath))


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
