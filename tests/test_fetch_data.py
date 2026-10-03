import hashlib
import importlib.util
import zipfile
from pathlib import Path

_spec = importlib.util.spec_from_file_location("fetch_data", Path(__file__).resolve().parents[1] / "scripts" / "fetch_data.py")
fetch_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_data)

DIRECT = "https://drive.usercontent.google.com/download?id=1AbC-d_9&export=download&confirm=t"
VIRUS_SCAN_PAGE = """<html><body><p>Google Drive can't scan this file for viruses.</p>
<form id="download-form" action="https://drive.usercontent.google.com/download" method="get">
<input type="submit" id="uc-download-link" value="Download anyway"/>
<input type="hidden" name="id" value="1AbC-d_9"><input type="hidden" name="export" value="download">
<input type="hidden" name="confirm" value="t"><input type="hidden" name="uuid" value="5e1f-77">
</form></body></html>"""


def test_drive_share_links_become_direct_downloads():
    for link in ("https://drive.google.com/file/d/1AbC-d_9/view?usp=sharing",
                 "https://drive.google.com/open?id=1AbC-d_9",
                 "https://drive.google.com/uc?export=download&id=1AbC-d_9"):
        assert fetch_data.direct_url(link) == DIRECT
    assert fetch_data.direct_url("https://example.com/b1.zip") == "https://example.com/b1.zip"


def test_virus_scan_page_gives_the_file_link():
    assert fetch_data.confirm_url(VIRUS_SCAN_PAGE) == DIRECT + "&uuid=5e1f-77"
    assert fetch_data.confirm_url('<form action="/signin"><input type="email" name="identifier"></form>') is None


def _photo_zip(tmp_path: Path) -> tuple[Path, str]:
    archive = tmp_path / "upload" / "photos.zip"
    archive.parent.mkdir()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("rooms/B1/photos/IMG_1.jpg", b"jpeg bytes")
    return archive, hashlib.sha256(archive.read_bytes()).hexdigest()


def test_fetch_checks_sha256_and_unpacks(tmp_path, capsys):
    archive, sha = _photo_zip(tmp_path)
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(f"capture_id,url,sha256\nphotos_B1,{archive.as_uri()},{sha}\nlater,TODO,TODO\napp,,\n",
                        encoding="utf-8")
    args = ["--manifest", str(manifest), "--dest", str(tmp_path / "captures")]
    assert fetch_data.main(args) == 0
    assert (tmp_path / "captures" / "photos_B1" / "rooms" / "B1" / "photos" / "IMG_1.jpg").read_bytes() == b"jpeg bytes"
    out = capsys.readouterr().out
    assert "[ok] photos_B1: sha256 verified" in out
    assert "[skip] later: no url in the manifest" in out and "[skip] app: no url in the manifest" in out
    assert fetch_data.main(args + ["photos_B1"]) == 0
    assert "[ok] photos_B1: already downloaded" in capsys.readouterr().out


def test_fetch_fails_on_sha256_mismatch(tmp_path, capsys):
    archive, _ = _photo_zip(tmp_path)
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(f"capture_id,url,sha256\nphotos_B1,{archive.as_uri()},{'0' * 64}\n", encoding="utf-8")
    assert fetch_data.main(["--manifest", str(manifest), "--dest", str(tmp_path / "captures")]) == 1
    assert "[fail] photos_B1: sha256 mismatch" in capsys.readouterr().err
