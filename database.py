from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, String, Numeric, DateTime, ForeignKey, func
from config import DATABASE_URL
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

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
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")

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
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Telegram message ID for editing
    chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Telegram chat ID for editing
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user: Mapped["User"] = relationship(back_populates="transactions")

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)