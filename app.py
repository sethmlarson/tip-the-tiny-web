from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session


db_engine = create_engine("sqlite:///app.sqlite", echo=True)
db = Session(db_engine)


class BaseModel(DeclarativeBase):
    pass


class Creator(BaseModel):
    __tablename__ = "creator"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column()
    display_name: Mapped[int] = mapped_column()
    web_url: Mapped[str] = mapped_column()
    feed_url: Mapped[Optional[str]] = mapped_column()
