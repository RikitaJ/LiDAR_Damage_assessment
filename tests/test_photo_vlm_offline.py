from pathlib import Path

from pipeline.integrations.azure_photo_vlm import estimate_room_from_photos


def test_photo_vlm_offline_without_keys(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "pipeline.integrations.azure_photo_vlm._env",
        lambda _name: None,
    )
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd8")
    est, w = estimate_room_from_photos([img])
    assert est is None
