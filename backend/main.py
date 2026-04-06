from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator

APP_NAME = "Calorie Tracker"


class FoodEntryBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    calories: int = Field(ge=0, le=50_000)
    meal: str = Field(min_length=1, max_length=40)


class FoodEntry(FoodEntryBase):
    id: int


class FoodEntryCreate(FoodEntryBase):
    @model_validator(mode="after")
    def normalize(self) -> FoodEntryCreate:
        self.name = self.name.strip()
        self.meal = self.meal.strip().title()
        return self


_store: dict[int, FoodEntry] = {}
_next_id = 1


def reset_storage() -> None:
    global _next_id
    _store.clear()
    _next_id = 1


app = FastAPI(title=APP_NAME, version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME}


@app.get("/entries", response_model=list[FoodEntry])
def list_entries() -> list[FoodEntry]:
    return list(_store.values())


@app.post("/entries", response_model=FoodEntry, status_code=status.HTTP_201_CREATED)
def create_entry(payload: FoodEntryCreate) -> FoodEntry:
    global _next_id
    entry = FoodEntry(id=_next_id, **payload.model_dump())
    _store[entry.id] = entry
    _next_id += 1
    return entry


@app.get("/entries/{entry_id}", response_model=FoodEntry)
def read_entry(entry_id: int) -> FoodEntry:
    entry = _store.get(entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return entry


@app.put("/entries/{entry_id}", response_model=FoodEntry)
def replace_entry(entry_id: int, payload: FoodEntryCreate) -> FoodEntry:
    if entry_id not in _store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    entry = FoodEntry(id=entry_id, **payload.model_dump())
    _store[entry_id] = entry
    return entry


@app.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int) -> Response:
    if entry_id not in _store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    del _store[entry_id]
    return Response(status_code=status.HTTP_204_NO_CONTENT)
