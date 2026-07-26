from sqlalchemy import Column, Integer, String

from .database import Base


class HealthCheck(Base):

    __tablename__ = "health_check"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    message = Column(
        String
    )