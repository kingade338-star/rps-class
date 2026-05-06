from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    history = relationship("GameHistory", back_populates="user")


class GameHistory(Base):
    __tablename__ = "game_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_choice = Column(String, nullable=False)
    computer_choice = Column(String, nullable=False)
    result = Column(String, nullable=False)  # "Win", "Lose", "Draw"
    played_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="history")