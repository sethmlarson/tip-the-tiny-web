import urllib.parse
from datetime import UTC, datetime
from typing import Optional

from flask import Flask, render_template
from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.types import DateTime, TypeDecorator

db_engine = create_engine("sqlite:///app.sqlite", echo=True)
db = Session(db_engine)
web = Flask(__name__)


class TzAwareDatetime(TypeDecorator):
    """Datetime that forces timezone-aware datetimes"""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not isinstance(value, datetime):
                raise TypeError("expected datetime.datetime")
            elif value.tzinfo is None:
                raise ValueError("naive datetime is disallowed")
            return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            else:
                value = value.astimezone(UTC)
        return value


class utcnow(FunctionElement):
    """utcnow that forces timezone awareness"""

    inherit_cache = True
    type = TzAwareDatetime()


@compiles(utcnow)
def default_sql_utcnow(element, compiler, **kw):
    """Assume, by default, time zones work correctly."""
    return "CURRENT_TIMESTAMP"


@compiles(utcnow, "sqlite")
def sqlite_sql_utcnow(element, compiler, **kw):
    """SQLite DATETIME('NOW') returns a correct `datetime.datetime` but does not
    add milliseconds to it.

    Directly call STRFTIME with the final %f modifier in order to get those.
    """
    return "(STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW'))"


class BaseModel(DeclarativeBase):
    pass


class Creator(BaseModel):
    __tablename__ = "creators"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(nullable=False)
    display_name: Mapped[str] = mapped_column(nullable=False)
    web_url: Mapped[str] = mapped_column(nullable=False)
    feed_url: Mapped[Optional[str]] = mapped_column(default=None)
    payment_methods: Mapped[list["PaymentMethod"]] = relationship(
        back_populates="creator", cascade="all, delete-orphan"
    )


class PaymentMethod(BaseModel):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column()
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    creator: Mapped["Creator"] = relationship(back_populates="payment_methods")
    payments: Mapped[list["Payment"]] = relationship(back_populates="payment_method")

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
    def display_name(self) -> str:
        raise NotImplementedError()

    @property
    def html_url(self) -> str:
        """Return the web URL for the creator's payment method"""
        raise NotImplementedError()


class GitHubSponsorsPaymentMethod(PaymentMethod):
    __tablename__ = "payment_methods_github_sponsors"

    id: Mapped[int] = mapped_column(ForeignKey("payment_methods.id"), primary_key=True)
    github_id: Mapped[int] = mapped_column(nullable=False)
    github_login: Mapped[str] = mapped_column(nullable=False)

    __mapper_args__ = {"polymorphic_identity": "payment_methods_github_sponsors"}

    @property
    def display_name(self) -> str:
        return "GitHub Sponsors"

    @property
    def html_url(self) -> str:
        return f"https://github.com/sponsors/{urllib.parse.quote(self.github_login)}"


class PatreonPaymentMethod(PaymentMethod):
    __tablename__ = "payment_methods_patreon"

    id: Mapped[int] = mapped_column(ForeignKey("payment_methods.id"), primary_key=True)
    patreon_creator_slug: Mapped[str] = mapped_column(nullable=False)

    __mapper_args__ = {"polymorphic_identity": "payment_methods_patreon"}

    @property
    def display_name(self) -> str:
        return "Patreon"

    @property
    def html_url(self) -> str:
        return f"https://patreon.com/c/{urllib.parse.quote(self.patreon_creator_slug)}"


class Payment(BaseModel):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        type_=TzAwareDatetime, nullable=False, default=utcnow()
    )
    payment_amount: Mapped[int] = mapped_column(nullable=False)

    payment_method: Mapped[PaymentMethod] = relationship(back_populates="payments")
    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_methods.id"), nullable=False
    )


@web.route("/")
def index():
    creators = db.query(Creator).all()
    creator_to_patreons = {}
    for patreon_payment in db.query(PatreonPaymentMethod).all():
        creator_to_patreons[patreon_payment.creator_id] = patreon_payment

    return render_template(
        "index.html", creators=creators, patreons=creator_to_patreons
    )
