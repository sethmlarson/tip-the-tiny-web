import typing
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Literal, Optional, get_args

from flask import Flask, make_response, render_template, request
from sqlalchemy import ForeignKey, create_engine, func
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    joinedload,
    mapped_column,
    relationship,
)
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.types import DateTime, Enum, TypeDecorator

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
    supporters: Mapped[list["SupporterToCreator"]] = relationship(
        back_populates="creator"
    )


class BudgetAllocation(BaseModel):
    __tablename__ = "budget_allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    supporter_id: Mapped[int] = mapped_column(
        ForeignKey("supporters.id"), nullable=False
    )
    supporter: Mapped["Supporter"] = relationship(back_populates="budget_allocs")
    allocation_amount: Mapped[int] = mapped_column(nullable=False)
    undistributed_amount: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        type_=TzAwareDatetime, nullable=False, default=utcnow()
    )


class Supporter(BaseModel):
    __tablename__ = "supporters"

    id: Mapped[int] = mapped_column(primary_key=True)
    budget_per_month: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        type_=TzAwareDatetime, nullable=False, default=utcnow()
    )
    supported_creators: Mapped[list["SupporterToCreator"]] = relationship()
    payments: Mapped[list["Payment"]] = relationship(back_populates="supporter")
    budget_allocs: Mapped[list["BudgetAllocation"]] = relationship(
        back_populates="supporter"
    )


class SupporterToCreator(BaseModel):
    __tablename__ = "supporter_to_creator"

    supporter_id: Mapped[int] = mapped_column(
        ForeignKey("supporters.id"), primary_key=True
    )
    supporter: Mapped["Supporter"] = relationship(back_populates="supported_creators")
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"), primary_key=True)
    creator: Mapped["Creator"] = relationship(back_populates="supporters")

    want_to_pay: Mapped[bool] = mapped_column(nullable=False, default=False)
    minimum_payment_per_month: Mapped[int] = mapped_column(nullable=False, default=0)
    payment_amount_outstanding: Mapped[int] = mapped_column(nullable=False, default=0)


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

    def supported_payment_amounts(self) -> list[int]:
        """
        List of possible payment amounts. An amount of '0' means
        that one-time payments of >= self.minimum_one_time_payment_amount
        is allowed.
        """
        payment_amounts = []
        if self.supports_one_time_payments:
            payment_amounts.append(0)
        return payment_amounts

    @property
    def display_name(self) -> str:
        raise NotImplementedError()

    @property
    def html_url(self) -> str:
        """Return the web URL for the creator's payment method"""
        raise NotImplementedError()

    def reify(
        self,
    ) -> typing.Union["GitHubSponsorsPaymentMethod", "PatreonPaymentMethod"]:
        if self.type == "payment_methods_github_sponsors":
            payment_cls = GitHubSponsorsPaymentMethod
        elif self.type == "payment_methods_patreon":
            payment_cls = PatreonPaymentMethod
        else:
            raise ValueError(f"Unknown PaymentMethod.type: {self.type}")
        return db.query(payment_cls).where(payment_cls.id == self.id).first()


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

    def supported_payment_amounts(self) -> list[int]:
        return [0, 500, 1000]

    @property
    def display_name(self) -> str:
        return "Patreon"

    @property
    def html_url(self) -> str:
        return f"https://patreon.com/c/{urllib.parse.quote(self.patreon_creator_slug)}"


PaymentState = Literal["next", "unpaid", "paid"]


class Payment(BaseModel):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[PaymentState] = mapped_column(
        Enum(
            *get_args(PaymentState),
            name="payment_status",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default="unpaid",
    )
    created_at: Mapped[datetime] = mapped_column(
        type_=TzAwareDatetime, nullable=False, default=utcnow()
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        type_=TzAwareDatetime,
        nullable=True,
        default=None,
    )
    payment_amount: Mapped[int] = mapped_column(nullable=False)

    payment_method: Mapped[PaymentMethod] = relationship(back_populates="payments")
    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_methods.id"), nullable=False
    )
    supporter: Mapped["Supporter"] = relationship(back_populates="payments")
    supporter_id: Mapped[int] = mapped_column(
        ForeignKey("supporters.id"), nullable=False
    )


def calculate_next_budget_alloc(supporter: Supporter) -> BudgetAllocation | None:
    with db.begin(nested=True):
        last_budget_alloc = (
            db.query(BudgetAllocation)
            .where(BudgetAllocation.supporter_id == supporter.id)
            .order_by(BudgetAllocation.created_at.desc())
            .first()
        )
        if last_budget_alloc is None:
            # This guarantees that if someone clicks the "Distribute"
            # button on their first day, it distributes exactly their
            # monthly budget to every creator instead of zero.
            alloc_amount = supporter.budget_per_month
        else:
            last_allocated_at = last_budget_alloc.created_at
            now_in_utc = datetime.now(tz=UTC)
            budget_per_day = int(supporter.budget_per_month * 12 // 360)
            days_since_last_alloc = (now_in_utc - last_allocated_at).total_seconds() / (
                24 * 60 * 60
            )
            alloc_amount = (
                int(budget_per_day * days_since_last_alloc)
                + last_budget_alloc.undistributed_amount
            )

        # No money to allocate!
        if alloc_amount <= 0:
            return None

        number_of_supported_creators = (
            db.query(SupporterToCreator)
            .where(
                SupporterToCreator.supporter_id == supporter.id,
                SupporterToCreator.want_to_pay,
            )
            .count()
        )
        # Don't allocate if no supported creators.
        if number_of_supported_creators <= 0:
            return None

        return BudgetAllocation(
            supporter_id=supporter.id,
            allocation_amount=alloc_amount,
        )


def distribute_budget_alloc(
    supporter: Supporter, budget_alloc: BudgetAllocation
) -> None:
    """Distributes an allocation of budget to creators"""
    with db.begin(nested=True):
        # Get all the creators that we want to pay.
        supporter_to_creators = (
            db.query(SupporterToCreator)
            .where(
                SupporterToCreator.supporter_id == supporter.id,
                SupporterToCreator.want_to_pay,
            )
            .all()
        )

        # Not yet paying any creators, abort!
        if not supporter_to_creators:
            return

        # Calculate how much budget we're allocating per creator.
        number_of_creators = len(supporter_to_creators)
        budget_per_creator = int(budget_alloc.allocation_amount // number_of_creators)

        # Less than a cent per creator? Abort!
        if budget_per_creator < 1:
            return

        # Distribute the budget
        for supporter_to_creator in supporter_to_creators:
            supporter_to_creator.payment_amount_outstanding += budget_per_creator

        # Commit the BudgetAllocation to the record
        # after updating how much we actually distributed.
        distributed_amount = budget_per_creator * number_of_creators
        budget_alloc.undistributed_amount = (
            budget_alloc.allocation_amount - distributed_amount
        )
        budget_alloc.allocation_amount = distributed_amount
        db.add(budget_alloc)
        db.commit()


@web.route("/")
def index():
    supporter = db.query(Supporter).options(joinedload(Supporter.payments)).first()
    supporter_to_creators = (
        db.query(SupporterToCreator)
        .join(Creator, onclause=SupporterToCreator.creator_id == Creator.id)
        .options(
            joinedload(SupporterToCreator.creator).joinedload(Creator.payment_methods)
        )
        .where(SupporterToCreator.supporter_id == supporter.id)
        .all()
    )
    next_payments = dict(
        db.query(PaymentMethod.creator_id, func.sum(Payment.payment_amount))
        .where(Payment.supporter_id == supporter.id, Payment.state == "next")
        .join(PaymentMethod)
        .group_by(PaymentMethod.creator_id)
        .all()
    )
    supporter_to_creators = sorted(
        supporter_to_creators,
        key=lambda s2c: (
            not s2c.want_to_pay,
            -s2c.payment_amount_outstanding,
            s2c.creator.display_name.lower(),
            s2c.creator.slug,
        ),
    )
    paid_to_date = (
        db.query(func.sum(Payment.payment_amount))
        .where(Payment.supporter_id == supporter.id, Payment.state == "paid")
        .scalar()
        or 0
    )
    total_payment_amount_outstanding = (
        db.query(func.sum(SupporterToCreator.payment_amount_outstanding))
        .where(SupporterToCreator.supporter_id == supporter.id)
        .scalar()
    ) or 0
    next_budget_alloc = calculate_next_budget_alloc(supporter)
    next_budget = next_budget_alloc.allocation_amount if next_budget_alloc else 0
    return render_template(
        "index.html",
        str=str,
        sum=sum,
        len=len,
        supporter=supporter,
        supporter_to_creators=supporter_to_creators,
        next_budget=next_budget,
        next_payments=next_payments,
        paid_to_date=paid_to_date,
        total_payment_amount_outstanding=total_payment_amount_outstanding,
    )


@web.route("/creators/<creator_slug>", methods=["GET"])
def creator(creator_slug: str):
    creator = (
        db.query(Creator)
        .options(joinedload(Creator.payment_methods))
        .where(Creator.slug == creator_slug)
        .first()
    )
    if creator is None:
        return make_response("", 404)
    supporter = db.query(Supporter).first()
    supporter_to_creator = (
        db.query(SupporterToCreator)
        .where(
            SupporterToCreator.creator_id == creator.id,
            SupporterToCreator.supporter_id == supporter.id,
        )
        .first()
    )
    return render_template(
        "creator.html", supporter_to_creator=supporter_to_creator, creator=creator
    )


def get_s2c_by_slug(creator_slug: str) -> SupporterToCreator | None:
    supporter = db.query(Supporter).first()
    supporter_to_creators = (
        db.query(SupporterToCreator)
        .options(joinedload(SupporterToCreator.creator))
        .join(Creator)
        .where(
            SupporterToCreator.supporter_id == supporter.id,
            Creator.slug == creator_slug,
        )
        .first()
    )
    return supporter_to_creators


@web.route("/api/creators/<creator_slug>/want-to-pay", methods=["PUT"])
def api_creators_want_to_pay(creator_slug: str):
    if (supporter_to_creators := get_s2c_by_slug(creator_slug)) is None:
        return make_response("", 404)
    try:
        checked = request.form["value"] == "true"
    except KeyError:
        checked = False
    supporter_to_creators.want_to_pay = checked
    db.commit()
    return make_response("", 200)


@web.route("/api/creators/<creator_slug>/minimum-payment-per-month", methods=["PUT"])
def api_creators_minimum_payment_per_month(creator_slug: str):
    if (supporter_to_creators := get_s2c_by_slug(creator_slug)) is None:
        return make_response("", 404)
    try:
        # Convert to cents.
        min_per_month = int(request.form["value"]) * 100
        if min_per_month < 0:
            raise ValueError("Minimum payment per month must be positive")
    except (KeyError, ValueError):
        return make_response("", 400)
    supporter_to_creators.minimum_payment_per_month = min_per_month
    db.commit()
    return make_response("", 200)


@web.route("/api/supporters/distribute-budget", methods=["POST"])
def api_supporters_distribute_budget():
    if not (supporter := db.query(Supporter).first()):
        return make_response("", 404)
    with db.begin(nested=True):
        budget_alloc = calculate_next_budget_alloc(supporter)
        if budget_alloc is None:
            return make_response("", 200)
        distribute_budget_alloc(supporter, budget_alloc)
    resp = make_response("", 200)
    resp.headers["HX-Refresh"] = "true"
    return resp


@web.route("/api/supporters/budget-per-month", methods=["PUT"])
def api_supporters_budget_per_month():
    if not (supporter := db.query(Supporter).first()):
        return make_response("", 404)
    try:
        # Convert to cents.
        budget_per_month = int(request.form["value"]) * 100
        if budget_per_month < 0:
            raise ValueError("Budget per month must be positive")
    except (KeyError, ValueError):
        return make_response("", 400)
    supporter.budget_per_month = budget_per_month
    db.commit()
    return make_response("", 200)
