
from sqlalchemy import Integer, String, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ChargingRequestDB(Base):
    __tablename__ = "charging_requests"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    household: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )

    energy: Mapped[float] = mapped_column(
        Float, nullable=False
    )

    power: Mapped[float] = mapped_column(
        Float, nullable=False
    )

    deadline: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
