import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, String, Integer, Numeric, DateTime, Boolean, ForeignKey, func, inspect, text
from config import DATABASE_URL
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Language preference
    language: Mapped[str] = mapped_column(String(5), server_default=text("'en'"), nullable=False)

    # Referral system
    referral_code: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    referred_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    referral_earnings: Mapped[Decimal] = mapped_column(Numeric(28, 18), server_default=text("0"), nullable=False)
    referral_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)

    transactions: Mapped[List["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    skin_transactions: Mapped[List["SkinTransaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    changenow_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    from_currency: Mapped[str] = mapped_column(String, nullable=False)
    from_network: Mapped[str] = mapped_column(String, nullable=False)
    to_currency: Mapped[str] = mapped_column(String, nullable=False)
    to_network: Mapped[str] = mapped_column(String, nullable=False)
    amount_from: Mapped[Decimal] = mapped_column(Numeric(precision=28, scale=18), nullable=False)
    amount_expected: Mapped[Decimal] = mapped_column(Numeric(precision=28, scale=18), nullable=False)
    amount_to: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=28, scale=18), nullable=True)
    destination_address: Mapped[str] = mapped_column(String, nullable=False)
    deposit_address: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="waiting", nullable=False)
    provider: Mapped[str] = mapped_column(String, server_default=text("'swapzone'"), nullable=False)  # "swapzone" or "changenow"
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Telegram message ID for editing
    chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Telegram chat ID for editing
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user: Mapped["User"] = relationship(back_populates="transactions")

class SkinTransaction(Base):
    __tablename__ = "skin_transactions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # DMarket details
    dmarket_offer_id: Mapped[str] = mapped_column(String, nullable=False)  # DMarket item offer ID
    skin_name: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "AK-47 | Redline (Field-Tested)"
    skin_price_usd: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2), nullable=False)  # Price in USD on DMarket

    # Payment details
    pay_currency: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "btc"
    pay_network: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "btc"
    pay_amount: Mapped[Decimal] = mapped_column(Numeric(precision=28, scale=18), nullable=False)  # Amount in crypto
    deposit_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Where user sends crypto
    changenow_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # ChangeNow exchange ID if conversion needed

    # Steam delivery
    steam_trade_url: Mapped[str] = mapped_column(String, nullable=False)
    trade_offer_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Steam trade offer ID

    # Status tracking
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    # Statuses: pending, payment_waiting, payment_received, purchasing, trade_sent, completed, failed, refunded

    # Telegram message tracking
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="skin_transactions")


class PromoCode(Base):
    __tablename__ = "promo_codes"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # e.g., "WELCOME"
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False)  # e.g., 50 (50% off fees)
    max_uses: Mapped[int] = mapped_column(Integer, server_default=text("100"), nullable=False)  # total uses allowed
    uses_per_user: Mapped[int] = mapped_column(Integer, server_default=text("3"), nullable=False)  # uses per user
    current_uses: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)  # total times used
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # optional expiry
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserPromo(Base):
    __tablename__ = "user_promos"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    promo_code_id: Mapped[int] = mapped_column(ForeignKey("promo_codes.id"), nullable=False)
    uses_remaining: Mapped[int] = mapped_column(Integer, nullable=False)  # decrements on each exchange
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceAlert(Base):
    __tablename__ = "price_alerts"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "btc", "eth", "ton"
    direction: Mapped[str] = mapped_column(String, nullable=False)  # "above" or "below"
    target_price: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)  # USD price
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Mapping from SQLAlchemy types to PostgreSQL DDL types
def _sa_type_to_ddl(sa_type) -> str:
    """Convert a SQLAlchemy column type to a PostgreSQL DDL string."""
    type_name = type(sa_type).__name__
    if type_name == "BigInteger":
        return "BIGINT"
    elif type_name == "String":
        return "VARCHAR"
    elif type_name == "Numeric":
        p = getattr(sa_type, "precision", None)
        s = getattr(sa_type, "scale", None)
        if p and s:
            return f"NUMERIC({p},{s})"
        return "NUMERIC"
    elif type_name == "DateTime":
        if getattr(sa_type, "timezone", False):
            return "TIMESTAMPTZ"
        return "TIMESTAMP"
    elif type_name == "Integer":
        return "INTEGER"
    elif type_name == "Boolean":
        return "BOOLEAN"
    elif type_name == "Text":
        return "TEXT"
    else:
        return "VARCHAR"


def _migrate_tables(connection):
    """Inspect existing tables and ADD any missing columns. Never drops anything."""
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            # Table doesn't exist at all — create it
            logger.info(f"  Creating new table: {table_name}")
            table.create(connection)
            continue

        # Table exists — check for missing columns
        existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name not in existing_columns:
                # Build ALTER TABLE ADD COLUMN statement
                col_type = _sa_type_to_ddl(column.type)
                nullable = "NULL" if column.nullable else "NOT NULL"
                default = ""
                if column.server_default is not None:
                    # Compile the server_default to a SQL string for the current dialect
                    default_arg = column.server_default.arg
                    if hasattr(default_arg, 'text'):
                        # It's a plain text clause (e.g. text("0"))
                        default = f" DEFAULT {default_arg.text}"
                    else:
                        # It's a SQL function (e.g. func.now()) — compile it
                        compiled = default_arg.compile(dialect=connection.dialect)
                        default = f" DEFAULT {compiled}"
                elif column.nullable:
                    default = " DEFAULT NULL"

                stmt = f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {col_type} {nullable}{default}'
                logger.info(f"  Adding column: {table_name}.{column.name} ({col_type})")
                connection.execute(text(stmt))


async def migrate_db():
    """Safely migrate the database: create missing tables and add missing columns.
    Never drops tables or columns — existing data is preserved."""
    async with engine.begin() as conn:
        await conn.run_sync(_migrate_tables)