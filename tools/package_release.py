"""Package IaC Genius Community Edition.

  python tools/package_release.py --spot dist/iacgenius-ce-spot.zip   # Spot host archive (Terraform source_zip)

Archives use fixed timestamps and the *committed* bytes (read from the git index), so identical source gives
identical bytes regardless of checkout line endings. Nothing is uploaded and no credentials are read.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPOT_PARTS = ["profiles/iacgenius", "deploy/aws-single/host.py",
              "deploy/aws-single/install-terraform-guidance.sh", "toolchain/install-toolchain.sh",
              "contracts", "LICENSE", "NOTICE"]
SKIP = {"__pycache__", ".terraform", ".pytest_cache"}


def files(parts):
    for part in parts:
        path = ROOT / part
        candidates = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        for p in candidates:
            if not any(s in p.parts for s in SKIP) and not p.name.endswith((".pyc", "local.json")):
                yield p


def committed_blobs(paths) -> dict:
    relative = sorted({path.relative_to(ROOT).as_posix() for path in paths})
    query = "".join(f":{name}\n" for name in relative).encode()
    result = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT, input=query, capture_output=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr.decode("utf-8", "replace")[:300] or "git cat-file failed")
    blobs, position, out = {}, 0, result.stdout
    for name in relative:
        end = out.index(b"\n", position)
        header = out[position:end].decode()
        position = end + 1
        if header.endswith(" missing"):
            raise SystemExit(f"{name} is not in the git index; add it before packaging a release")
        size = int(header.rsplit(" ", 1)[1])
        blobs[name] = out[position:position + size]
        position += size + 1
    return blobs


def write_zip(output: Path, paths) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    entries = committed_blobs(paths)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            entry = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, entries[name])
    return hashlib.sha256(output.read_bytes()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spot", type=Path, required=True, help="write the Spot host archive to this path")
    args = parser.parse_args()
    print(json.dumps({"archive": str(args.spot), "sha256": write_zip(args.spot, files(SPOT_PARTS))}))