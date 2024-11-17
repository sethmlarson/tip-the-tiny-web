import urllib.parse
from typing import Optional

from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

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
    payment_methods: Mapped[list["PaymentMethod"]] = relationship(
        back_populates="creator", cascade="all, delete-orphan"
    )


class PaymentMethod(BaseModel):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column()
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator.id"))
    creator: Mapped["Creator"] = relationship(back_populates="payment_methods")

    supports_payment_comments: Mapped[bool] = mapped_column(default=False)
    supports_tiers: Mapped[bool] = mapped_column(default=False)
    supports_one_time_payments: Mapped[bool] = mapped_column(default=False)
    minimum_one_time_payment_amount: Mapped[int] = mapped_column(default=0)

    __mapper_args__ = {
        "polymorphic_identity": "payment_method",
        "polymorphic_on": "type",
    }

    def refresh_from_provider(self) -> None:
        """Refreshes the metadata from the provider,
        such as tiers and whether one-time payments are supported.
        """

    @property
    def html_url(self) -> str:
        """Return the web URL for the creator's payment method"""
        raise NotImplementedError()


class GitHubSponsorsPaymentMethod(PaymentMethod):
    __tablename__ = "payment_methods_github_sponsors"

    id: Mapped[int] = mapped_column(ForeignKey("payment_methods.id"), primary_key=True)
    github_id: Mapped[int] = mapped_column()
    github_login: Mapped[str] = mapped_column()

    __mapper_args__ = {"polymorphic_identity": "payment_methods_github_sponsors"}

    @property
    def html_url(self) -> str:
        return f"https://github.com/sponsors/{urllib.parse.quote(self.github_login)}"
