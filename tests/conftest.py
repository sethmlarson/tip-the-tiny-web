import pytest
from sqlalchemy.orm import Session

from app import BaseModel, db_engine


@pytest.fixture(scope="function")
def test_db_session() -> Session:
    BaseModel.metadata.create_all(db_engine)
    try:
        with Session(bind=db_engine) as session:
            yield session
    finally:
        BaseModel.metadata.drop_all(db_engine)
