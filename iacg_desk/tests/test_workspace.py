import json
import zipfile
from pathlib import Path

from iacg_desk import build_sheet, resolver, versions, workspace


def _confirmed_mission(store, mid, tree):
    store.update_mission(mid, tree=str(tree))
    resolver.resolve(store, mid, stated={"environment": "prod"}, ask=False)
    versions.pin(store, mid)
    (tree / "main.tf").write_text('resource "aws_s3_bucket" "b" {\n  bucket = "demo"\n}\n', encoding="utf-8")
    return build_sheet.confirm(store, mid, confirmed_by="tester")


def test_sync_writes_provenance_folder(store, mid, tree):
    _confirmed_mission(store, mid, tree)
    result = workspace.sync(store, mid)
    work = tree / "work"
    assert (work / "ledger.json").is_file()
    sheet = json.loads((work / "build-sheet.json").read_text(encoding="utf-8"))
    assert sheet["confirmed_by"] == "tester" and sheet["status"] == "confirmed"
    assert (tree / "README.md").is_file()
    manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mission_id"] == mid and manifest["target_locked"] is True
    assert "work/ledger.json" in result["files"]


def test_package_zips_whole_folder_minus_providers(store, mid, tree):
    _confirmed_mission(store, mid, tree)
    (tree / ".terraform").mkdir()
    (tree / ".terraform" / "provider.bin").write_bytes(b"\x00" * 100)
    result = workspace.package(store, mid)
    zp = Path(result["zip"])
    assert zp.is_file() and zp.name == f"{mid}.zip"
    with zipfile.ZipFile(zp) as zf:
        names = zf.namelist()
    assert f"{mid}/main.tf" in names
    assert f"{mid}/work/ledger.json" in names
    assert f"{mid}/work/build-sheet.json" in names
    assert f"{mid}/README.md" in names
    assert not any(".terraform" in n for n in names)  # provider binaries excluded from the download
    assert result["bytes"] > 0


def test_package_without_tree_raises(store, mid):
    try:
        workspace.package(store, mid)
        raise AssertionError("package ran without a generated tree")
    except ValueError as exc:
        assert "tree" in str(exc)