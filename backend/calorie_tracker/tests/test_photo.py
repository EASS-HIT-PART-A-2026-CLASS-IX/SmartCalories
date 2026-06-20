from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from calorie_tracker.ai import vision as vision_module
from calorie_tracker.ai.vision import NutritionExtraction


@pytest.fixture
def fake_extraction(monkeypatch):
    async def _fake(image_path):
        return NutritionExtraction(
            name="Avocado toast",
            calories=320,
            protein_g=10,
            carb_g=32,
            fat_g=18,
            confidence=0.85,
            note="Whole-wheat bread + half avocado.",
        )

    monkeypatch.setattr(vision_module, "analyze_image", _fake)
    yield


@pytest.fixture
def fake_image_bytes() -> bytes:
    # Tiny valid JPEG (smallest possible). Doesn't need to be a real food image since vision is mocked.
    return bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffdb0043010909090c0b0c180d0d1832211c213232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232ffc00011080001000103012200021101031101ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc4007f10000201030302040305050404000017d010203040051112213141062207617122814232718a190a181c1d1e123617435517614525323a262624737e3f0a4f1c576b32482938394c1d1f01115a2363925a35663d2e3f2435363a4d4e565d6e6f74757677787a82838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda000c03010002110311003f00fbfd28a28a00ffd9"
    )


def test_photo_scan_returns_extraction_no_commit(
    client: TestClient, fake_extraction, fake_image_bytes
) -> None:
    files = {"file": ("meal.jpg", io.BytesIO(fake_image_bytes), "image/jpeg")}
    r = client.post("/photo/scan", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["extraction"]["name"] == "Avocado toast"
    assert body["extraction"]["calories"] == 320
    assert body["entry"] is None  # commit not requested


def test_photo_scan_commits_diary_entry(
    client: TestClient, fake_extraction, fake_image_bytes
) -> None:
    files = {"file": ("meal.jpg", io.BytesIO(fake_image_bytes), "image/jpeg")}
    r = client.post("/photo/scan?commit=true&meal=lunch", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["entry"]["name"] == "Avocado toast"
    assert body["entry"]["meal"] == "lunch"

    diary = client.get("/diary").json()
    assert any(d["source"] == "photo" for d in diary)


def test_uploaded_file_persisted_under_user_dir(
    client: TestClient, fake_extraction, fake_image_bytes, tmp_path, monkeypatch
) -> None:
    """Verify save_upload writes a file we can locate via the returned image_path."""
    from calorie_tracker.services import storage

    monkeypatch.setattr(storage, "uploads_root", lambda: tmp_path)
    files = {"file": ("meal.jpg", io.BytesIO(fake_image_bytes), "image/jpeg")}
    r = client.post("/photo/scan?commit=true&meal=lunch", files=files)
    assert r.status_code == 200
    image_path = r.json()["image_path"]
    assert Path(image_path).exists()
    assert str(tmp_path) in image_path
