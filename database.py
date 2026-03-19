import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, String, Integer, Float, ForeignKey
from dotenv import load_dotenv
from typing import List

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:sZXuCHMdyzrwoBzrkYOLKZfAoUtWnUCO@postgres.railway.internal:5432/railway")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String, nullable=True)

    balances: Mapped[List["Balance"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Balance(Base):
    __tablename__ = "balances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    asset: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    user: Mapped["User"] = relationship(back_populates="balances")

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)