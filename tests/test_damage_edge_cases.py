import json
from pathlib import Path

from pipeline.config import InputTier
from pipeline.damage.cache import write_image_hits
from pipeline.damage.detect import detect_damage_regions
from pipeline.damage.phase5 import run_damage_pipeline
from pipeline.damage.sanitize import filter_hits, sanitize_damage_regions, valid_hit
from pipeline.measure.intervals import with_interval


def _room(room_id: str, *, walls: list | None = None) -> dict:
    tier = InputTier.LIDAR
    wlist = walls
    if wlist is None:
        wlist = [
            {
                "id": f"{room_id}-W1",
                "length_m": with_interval(4.0, 0.1, notes="t", tier=tier, kind="wall"),
                "polyline_m": [[0.0, 0.0], [4.0, 0.0]],
                "openings": [],
            }
        ]
    return {
        "room_id": room_id,
        "name": room_id,
        "pose_world": {"translation_m": [0.0, 0.0, 0.0]},
        "ceiling_height_m": with_interval(2.5, 0.1, notes="t", tier=tier, kind="height"),
        "floor_area_m2": with_interval(12.0, 0.4, notes="t", tier=tier, kind="footprint"),
        "walls": wlist,
    }


def test_detect_no_rgb_stills(tmp_path: Path):
    regions, w = detect_damage_regions([_room("R1")], tmp_path, InputTier.LIDAR)
    assert regions == []
    assert any("no RGB" in x for x in w)


def test_detect_empty_rooms():
    regions, w = detect_damage_regions([], Path("."), InputTier.LIDAR)
    assert regions == []
    assert any("no rooms" in x for x in w)


def test_detect_corrupt_jpeg(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("pipeline.damage.cache.CACHE_DIR", tmp_path / "cache")
    cap = tmp_path / "cap"
    photos = cap / "rooms" / "R1" / "photos"
    photos.mkdir(parents=True)
    (photos / "bad.jpg").write_bytes(b"not-a-jpeg")
    regions, w = detect_damage_regions([_room("R1")], cap, InputTier.LIDAR)
    assert regions == []
    assert any("unreadable" in x for x in w)


def test_detect_skips_empty_file(tmp_path: Path):
    cap = tmp_path / "cap"
    photos = cap / "rooms" / "R1" / "photos"
    photos.mkdir(parents=True)
    (photos / "empty.jpg").write_bytes(b"")
    from pipeline.damage.detect import _sample_images

    assert _sample_images(cap, [_room("R1")]) == []
    regions, w = detect_damage_regions([_room("R1")], cap, InputTier.LIDAR)
    assert regions == []
    assert any("no RGB" in x for x in w)


def test_detect_single_still_warning(tmp_path: Path):
    cap = tmp_path / "cap"
    photos = cap / "rooms" / "R1" / "photos"
    photos.mkdir(parents=True)
    (photos / "one.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 400 + b"\xff\xd9")
    _, w = detect_damage_regions([_room("R1")], cap, InputTier.LIDAR)
    assert any("single RGB" in x for x in w)


def test_detect_room_without_walls(tmp_path: Path, monkeypatch):
    cap = tmp_path / "cap"
    photos = cap / "rooms" / "R1" / "photos"
    photos.mkdir(parents=True)
    img = photos / "a.jpg"
    img.write_bytes(b"x")
    hit = {
        "class": "water_stain",
        "u_center_frac": 0.5,
        "area_m2": 0.1,
        "score": 0.5,
        "source": "test",
    }
    monkeypatch.setattr("pipeline.damage.cache.CACHE_DIR", tmp_path / "cache")
    write_image_hits(img, [hit])
    room = _room("R1", walls=[])
    regions, w = detect_damage_regions([room], cap, InputTier.LIDAR)
    assert regions == []
    assert any("no walls" in x for x in w)


def test_depth_png_excluded(tmp_path: Path):
    cap = tmp_path / "cap"
    photos = cap / "rooms" / "R1" / "photos"
    photos.mkdir(parents=True)
    (photos / "frame_depth.png").write_bytes(b"\x89PNG")
    (photos / "real.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x01" * 200 + b"\xff\xd9")
    from pipeline.damage.detect import _sample_images

    paths = _sample_images(cap, [_room("R1")])
    names = {p.name for p in paths}
    assert "real.jpg" in names
    assert "frame_depth.png" not in names


def test_invalid_cached_hit_filtered():
    good = {"class": "water_stain", "u_center_frac": 0.5, "area_m2": 0.1, "score": 0.5}
    bad = {"class": "alien", "u_center_frac": "nope"}
    out, w = filter_hits([good, bad])
    assert len(out) == 1
    assert w


def test_stale_cache_version_ignored(tmp_path: Path, monkeypatch):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"img-bytes")
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr("pipeline.damage.cache.CACHE_DIR", cache)
    from pipeline.damage import cache as cache_mod

    key_path = cache_mod._cache_file(img)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps({"version": "old", "hits": [{"class": "water_stain"}]}), encoding="utf-8")
    assert cache_mod.read_image_hits(img) is None


def test_sanitize_drops_bad_region():
    tier = InputTier.LIDAR
    bad = {"id": "D1", "class": "unknown", "surface_id": "W1", "polygon_surface": [[0, 0], [1, 0], [1, 1]]}
    out, w = sanitize_damage_regions([bad], tier)
    assert out == []
    assert w


def test_run_damage_pipeline_empty_rooms():
    s, r, c, sc, w, lim = run_damage_pipeline([], [], Path("."), InputTier.LIDAR)
    assert s == [] and r == [] and sc == []
    assert any("empty rooms" in x for x in w)


def test_r39_downgrades_damage(tmp_path: Path, monkeypatch):
    cap = tmp_path / "cap"
    photos = cap / "rooms" / "R1" / "photos"
    photos.mkdir(parents=True)
    img = photos / "a.jpg"
    img.write_bytes(b"cached-img")
    monkeypatch.setattr("pipeline.damage.cache.CACHE_DIR", tmp_path / "cache")
    write_image_hits(
        img,
        [
            {
                "class": "water_stain",
                "u_center_frac": 0.4,
                "area_m2": 0.12,
                "bottom_above_floor_m": 0.15,
                "score": 0.7,
                "source": "hsv_stain_heuristic_v1",
            }
        ],
    )
    _, regions, _, _, w, lim = run_damage_pipeline(
        [_room("R1")],
        ["R39: mirror behind wall — exclude geometry"],
        cap,
        InputTier.LIDAR,
    )
    assert regions
    assert regions[0].get("surface_review") == "r39_mirror_glass"
    assert regions[0]["score"] <= 0.32
    assert any("R39" in x for x in w)
    assert any("R39" in x or "mirror" in x for x in lim)


def test_multi_room_images_use_room_folder(tmp_path: Path, monkeypatch):
    cap = tmp_path / "cap"
    for rid in ("bed", "hall"):
        photos = cap / "rooms" / rid / "photos"
        photos.mkdir(parents=True)
        img = photos / "shot.jpg"
        img.write_bytes(f"{rid}-bytes".encode())
    monkeypatch.setattr("pipeline.damage.cache.CACHE_DIR", tmp_path / "cache")
    for rid in ("bed", "hall"):
        img = cap / "rooms" / rid / "photos" / "shot.jpg"
        write_image_hits(
            img,
            [
                {
                    "class": "water_stain",
                    "u_center_frac": 0.3,
                    "area_m2": 0.1,
                    "bottom_above_floor_m": 0.2,
                    "score": 0.5,
                    "source": "test",
                }
            ],
        )
    rooms = [_room("bed"), _room("hall")]
    regions, _ = detect_damage_regions(rooms, cap, InputTier.LIDAR)
    assert len(regions) == 2
    surfaces = {r["surface_id"] for r in regions}
    assert "bed-W1" in surfaces and "hall-W1" in surfaces


def test_opencv_missing_graceful(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("pipeline.damage.cache.CACHE_DIR", tmp_path / "cache")
    cap = tmp_path / "cap"
    photos = cap / "rooms" / "R1" / "photos"
    photos.mkdir(parents=True)
    (photos / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 300 + b"\xff\xd9")

    import pipeline.damage.detect as detect_mod

    monkeypatch.setattr(
        detect_mod,
        "_compute_image_hits",
        lambda _p, **_: ([], ["damage: opencv unavailable — image heuristics skipped"]),
    )
    regions, w = detect_damage_regions([_room("R1")], cap, InputTier.LIDAR)
    assert regions == []
    assert any("opencv" in x for x in w)


def test_valid_hit_helper():
    assert valid_hit({"class": "crack", "u_center_frac": 0.5, "area_m2": 0.1, "score": 0.5})
    assert not valid_hit({"class": "crack", "area_m2": "x"})
