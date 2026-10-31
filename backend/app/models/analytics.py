import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SearchLog(Base):
    """One first-page search event.

    Only the first page of a search is logged; loading more results should not
    inflate demand. `normalized_query` is used for keyword grouping while
    `query` keeps what the user actually typed.
    """

    __tablename__ = "search_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    query: Mapped[str | None] = mapped_column(String(160), nullable=True)
    normalized_query: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subcategory_id: Mapped[int | None] = mapped_column(
        ForeignKey("subcategories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    results_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="search", server_default="search"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True
    )


class QuoteDelivery(Base):
    """A quote request sent to one business.

    `seen_at` is set when the matching owner inbox renders the request.
    `responded_at` is set when the business submits or declines an offer.
    `round`/`source` keep each dispatch wave auditable so the retry worker can
    decide whether the latest wave was engaged.
    """

    __tablename__ = "quote_deliveries"
    __table_args__ = (
        sa.UniqueConstraint("request_id", "business_id", name="uq_quote_delivery_request_business"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quote_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    round: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1", index=True
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="auto", server_default="auto"
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True
    )
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class QuoteDispatchRun(Base):
    """One auditable dispatch wave for a quote request.

    The engine is deliberately database-first: Redis wakes the worker quickly,
    but the quote row itself is the durable schedule. Each wave records how many
    candidates existed, how many owners were actually targeted and why the wave
    ran (initial / retry / manual / forced).
    """

    __tablename__ = "quote_dispatch_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quote_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="initial")
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detail: Mapped[dict] = mapped_column(sa.JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True
    )
