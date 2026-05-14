from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sex: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    activity_level: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    goal: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    diet_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    allergies_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    excluded_products_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    health_flags_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    daily_calories_target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_protein_target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_fat_target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_carbs_target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_fiber_target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_water_target_ml: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped[Optional["UserProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    reminders: Mapped[List["Reminder"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    meal_logs: Mapped[List["MealLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    daily_summaries: Mapped[List["DailySummary"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    ai_memories: Mapped[List["AIMemory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Questionnaire(Base):
    __tablename__ = "questionnaires"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="in_progress", index=True)
    answers_json: Mapped[str] = mapped_column(Text, default="{}")
    current_question_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    files: Mapped[List["QuestionnaireFile"]] = relationship(
        back_populates="questionnaire", cascade="all, delete-orphan"
    )
    participant_profiles: Mapped[List["ParticipantProfile"]] = relationship(
        back_populates="source_questionnaire"
    )


class QuestionnaireFile(Base):
    __tablename__ = "questionnaire_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    questionnaire_id: Mapped[int] = mapped_column(
        ForeignKey("questionnaires.id", ondelete="CASCADE"), index=True
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    file_id: Mapped[str] = mapped_column(String(512))
    file_unique_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    questionnaire: Mapped[Questionnaire] = relationship(back_populates="files")


class ParticipantProfile(Base):
    __tablename__ = "participant_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    questionnaire_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("questionnaires.id", ondelete="SET NULL"), nullable=True, index=True
    )
    questionnaire_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    profile_json: Mapped[str] = mapped_column(Text, default="{}")
    summary_text: Mapped[str] = mapped_column(Text, default="")
    risk_flags_text: Mapped[str] = mapped_column(Text, default="")
    coach_focus_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source_questionnaire: Mapped[Optional[Questionnaire]] = relationship(
        back_populates="participant_profiles"
    )
    notes: Mapped[List["ParticipantNote"]] = relationship(
        back_populates="participant_profile", cascade="all, delete-orphan"
    )


class ParticipantNote(Base):
    __tablename__ = "participant_notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    participant_profile_id: Mapped[int] = mapped_column(
        ForeignKey("participant_profiles.id", ondelete="CASCADE"), index=True
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    author_telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="admin")
    note_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    participant_profile: Mapped[ParticipantProfile] = relationship(back_populates="notes")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    goal: Mapped[str] = mapped_column(Text, default="")
    allergies: Mapped[str] = mapped_column(Text, default="")
    restrictions: Mapped[str] = mapped_column(Text, default="")
    household_size: Mapped[str] = mapped_column(String(32), default="")
    cooking_time: Mapped[str] = mapped_column(String(128), default="")
    budget: Mapped[str] = mapped_column(String(128), default="")
    equipment: Mapped[str] = mapped_column(Text, default="")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile")


class Dish(Base):
    __tablename__ = "dishes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    recipe_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    category_slug: Mapped[str] = mapped_column(String(64), index=True)
    category_title: Mapped[str] = mapped_column(String(128), default="")
    total_weight_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calories_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    protein_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fat_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    carbs_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fiber_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sugar_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sodium_mg_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    water_ml_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    micronutrients_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    prep_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    calories_100g: Mapped[float] = mapped_column(Float, default=0)
    protein_100g: Mapped[float] = mapped_column(Float, default=0)
    fat_100g: Mapped[float] = mapped_column(Float, default=0)
    carbs_100g: Mapped[float] = mapped_column(Float, default=0)
    fiber_100g: Mapped[float] = mapped_column(Float, default=0)
    sugar_100g: Mapped[float] = mapped_column(Float, default=0)
    sodium_mg_100g: Mapped[float] = mapped_column(Float, default=0)
    saturated_fat_100g: Mapped[float] = mapped_column(Float, default=0)
    water_ml_100g: Mapped[float] = mapped_column(Float, default=0)
    micronutrients_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    allergens_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MealLog(Base):
    __tablename__ = "meal_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal_type: Mapped[str] = mapped_column(String(32), default="snack")
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    dish_id: Mapped[Optional[int]] = mapped_column(ForeignKey("dishes.id"), nullable=True)
    custom_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    grams: Mapped[float] = mapped_column(Float, default=0)
    calories: Mapped[float] = mapped_column(Float, default=0)
    protein: Mapped[float] = mapped_column(Float, default=0)
    fat: Mapped[float] = mapped_column(Float, default=0)
    carbs: Mapped[float] = mapped_column(Float, default=0)
    fiber: Mapped[float] = mapped_column(Float, default=0)
    sugar: Mapped[float] = mapped_column(Float, default=0)
    sodium_mg: Mapped[float] = mapped_column(Float, default=0)
    water_ml: Mapped[float] = mapped_column(Float, default=0)
    micronutrients_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    raw_input_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="meal_logs")


class DailySummary(Base):
    __tablename__ = "daily_summary"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    calories_fact: Mapped[float] = mapped_column(Float, default=0)
    protein_fact: Mapped[float] = mapped_column(Float, default=0)
    fat_fact: Mapped[float] = mapped_column(Float, default=0)
    carbs_fact: Mapped[float] = mapped_column(Float, default=0)
    fiber_fact: Mapped[float] = mapped_column(Float, default=0)
    sugar_fact: Mapped[float] = mapped_column(Float, default=0)
    sodium_mg_fact: Mapped[float] = mapped_column(Float, default=0)
    water_ml_fact: Mapped[float] = mapped_column(Float, default=0)
    calories_target: Mapped[float] = mapped_column(Float, default=0)
    protein_target: Mapped[float] = mapped_column(Float, default=0)
    fat_target: Mapped[float] = mapped_column(Float, default=0)
    carbs_target: Mapped[float] = mapped_column(Float, default=0)
    fiber_target: Mapped[float] = mapped_column(Float, default=0)
    water_target_ml: Mapped[float] = mapped_column(Float, default=0)
    deficit_or_surplus: Mapped[float] = mapped_column(Float, default=0)
    ai_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="daily_summaries")


class AIMemory(Base):
    __tablename__ = "ai_memory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    memory_type: Mapped[str] = mapped_column(String(64), index=True)
    memory_key: Mapped[str] = mapped_column(String(128), index=True)
    memory_value: Mapped[str] = mapped_column(Text)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="ai_memories")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    intent: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="conversations")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    hour: Mapped[int] = mapped_column(Integer)
    minute: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fired_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    user: Mapped[User] = relationship(back_populates="reminders")
