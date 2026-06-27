"""Populate a rich, realistic demo dataset for the special user `demo-uid`.

Idempotent: every call deletes any existing demo data and rebuilds it anchored on today,
so the dashboard never goes stale. Designed to take <1s on Postgres.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlmodel import Session, delete, select

from ..models import (
    ChatMessage,
    ChatSession,
    FoodEntry,
    Meal,
    Preferences,
    Source,
    User,
    UserGoals,
    WaterLog,
)

DEMO_UID = "demo-uid"

_BREAKFASTS = [
    ("Greek yogurt + berries + granola", 380, 18, 50, 9),
    ("Veggie omelet (3 eggs)", 420, 28, 6, 30),
    ("Avocado toast + poached egg", 410, 16, 35, 22),
    ("Oatmeal with banana & peanut butter", 470, 14, 70, 15),
    ("Smoothie bowl (mango, spinach, oats)", 360, 12, 65, 6),
    ("Cottage cheese + honey + walnuts", 390, 24, 30, 18),
]
_LUNCHES = [
    ("Quinoa & roasted veg bowl", 580, 18, 78, 18),
    ("Falafel pita + tahini + salad", 640, 22, 80, 24),
    ("Caprese sandwich + side salad", 610, 24, 60, 28),
    ("Lentil soup + whole-grain roll", 520, 26, 70, 12),
    ("Grain bowl: bulgur, chickpea, feta, beet", 590, 22, 75, 18),
    ("Veggie wrap + hummus + olives", 550, 18, 60, 22),
]
_DINNERS = [
    ("Pasta primavera + parmesan", 720, 24, 90, 22),
    ("Stir-fry tofu + brown rice + broccoli", 640, 32, 75, 20),
    ("Baked salmon, sweet potato, asparagus", 680, 40, 50, 28),
    ("Margherita pizza (2 slices) + salad", 720, 28, 80, 28),
    ("Veggie curry + basmati rice + naan", 760, 22, 105, 22),
    ("Eggplant parm + garlic bread + greens", 780, 26, 80, 32),
]
_SNACKS = [
    ("Apple + almond butter", 220, 5, 30, 9),
    ("Hummus + carrot sticks", 180, 6, 22, 8),
    ("Greek yogurt + honey", 160, 12, 18, 4),
    ("Protein bar", 210, 15, 22, 7),
    ("Handful of mixed nuts", 200, 7, 8, 17),
    ("Dark chocolate square + tea", 110, 1, 12, 6),
]


def _ensure_user(session: Session) -> User:
    user = session.get(User, DEMO_UID)
    if user is None:
        user = User(
            uid=DEMO_UID,
            email="demo@smartcalories.local",
            display_name="Alex Demo",
            is_anonymous=False,
            role="user",
            timezone="America/New_York",
            locale="en",
        )
        session.add(user)
    return user


def _wipe_existing(session: Session) -> None:
    """Delete all rows the demo seeder owns. Order matters because of FKs."""
    session.exec(delete(ChatMessage).where(  # type: ignore[call-arg]
        ChatMessage.session_id.in_(  # type: ignore[attr-defined]
            select(ChatSession.id).where(ChatSession.user_uid == DEMO_UID)
        )
    ))
    for model in (ChatSession, FoodEntry, WaterLog):
        session.exec(delete(model).where(model.user_uid == DEMO_UID))  # type: ignore[arg-type]
    session.exec(delete(UserGoals).where(UserGoals.user_uid == DEMO_UID))  # type: ignore[arg-type]
    session.exec(delete(Preferences).where(Preferences.user_uid == DEMO_UID))  # type: ignore[arg-type]
    session.commit()


def _diary_rows(today: datetime) -> Iterable[FoodEntry]:
    rng = random.Random(42)
    for offset in range(30):
        day = today - timedelta(days=offset)
        for meal_enum, table, hour in (
            (Meal.breakfast, _BREAKFASTS, 8),
            (Meal.lunch, _LUNCHES, 13),
            (Meal.dinner, _DINNERS, 19),
        ):
            name, kcal, p, c, f = rng.choice(table)
            jitter = rng.randint(-5, 5)
            yield FoodEntry(
                user_uid=DEMO_UID,
                name=name,
                calories=kcal + jitter,
                protein_g=p,
                carb_g=c,
                fat_g=f,
                meal=meal_enum,
                eaten_at=day.replace(hour=hour, minute=rng.randint(0, 50)),
                source=Source.manual,
            )
        for _ in range(rng.randint(1, 2)):
            name, kcal, p, c, f = rng.choice(_SNACKS)
            yield FoodEntry(
                user_uid=DEMO_UID,
                name=name,
                calories=kcal,
                protein_g=p,
                carb_g=c,
                fat_g=f,
                meal=Meal.snack,
                eaten_at=day.replace(hour=rng.randint(10, 22), minute=rng.randint(0, 59)),
                source=Source.manual,
            )


def populate(session: Session) -> dict[str, int]:
    """Wipe + recreate the demo user's full dataset. Returns row counts inserted."""
    user = _ensure_user(session)
    _wipe_existing(session)
    counts = {
        "user": 1 if user else 0,
        "goals": 0,
        "preferences": 0,
        "food_entry": 0,
        "water_log": 0,
        "chat_session": 0,
        "chat_message": 0,
    }

    session.add(
        UserGoals(
            user_uid=DEMO_UID,
            daily_kcal=2200,
            protein_g=140,
            carb_g=240,
            fat_g=70,
            tdee=2300,
            activity_level="moderate",
            dietary_filters=["vegetarian"],
            weight_kg=75,
            height_cm=178,
            sex="male",
        )
    )
    counts["goals"] += 1

    session.add(
        Preferences(
            user_uid=DEMO_UID,
            theme="system",
            language="en",
            units="metric",
            notifications={},
        )
    )
    counts["preferences"] += 1

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    food_rows = list(_diary_rows(today))
    session.bulk_save_objects(food_rows)
    counts["food_entry"] += len(food_rows)

    rng = random.Random(7)
    water_rows: list[WaterLog] = []
    for offset in range(14):
        day = today - timedelta(days=offset)
        for hour in (9, 12, 15, 18, 21):
            water_rows.append(
                WaterLog(
                    user_uid=DEMO_UID,
                    ml=rng.choice([200, 250, 300, 350]),
                    logged_at=day.replace(hour=hour, minute=rng.randint(0, 59)),
                )
            )
    session.bulk_save_objects(water_rows)
    counts["water_log"] += len(water_rows)

    sessions_data = [
        (
            "Plan my week around 2200 kcal",
            [
                ("user", "Help me plan my meals this week — vegetarian, around 2200 kcal/day."),
                (
                    "assistant",
                    "Got it. Try Greek yogurt parfait for breakfast, quinoa bowls for lunch, and "
                    "rotating dinners. That keeps you near 2200 kcal with 140g protein.",
                ),
            ],
        ),
        (
            "/budget",
            [
                ("user", "/budget"),
                (
                    "assistant",
                    "You've got **820 kcal** left today (33g protein, 95g carb, 22g fat). "
                    "Try a veggie curry (760 kcal, 22g protein) — fits with room for a snack.",
                ),
            ],
        ),
    ]
    for title, messages in sessions_data:
        chat = ChatSession(user_uid=DEMO_UID, title=title)
        session.add(chat)
        session.flush()
        counts["chat_session"] += 1
        for role, content in messages:
            session.add(ChatMessage(session_id=chat.id, role=role, content=content))
            counts["chat_message"] += 1

    session.commit()
    return counts
