#!/usr/bin/env python3
"""
Upload the deposit files to a Zenodo draft, one at a time, resumably.

Why not the browser: dropping 27 files into the web form opens several parallel
connections and splits the upstream between them. A large file behind others goes
quiet long enough to be dropped, and restarts from zero. This uploads one file at
a time over a single connection, retries only the file that failed, and skips
whatever the draft already holds, so it can be stopped and re-run.

Setup
-----
1. zenodo.org -> profile -> Applications -> Personal access tokens -> New token,
   scopes `deposit:write` and `deposit:actions`. Copy the token once; Zenodo will
   not show it again.
2. Create the draft in the browser first (New upload -> Save draft) and read the
   record id from the URL, e.g. https://zenodo.org/uploads/1234567 -> 1234567.
3. Put the token in the environment, never in this file:

       $env:ZENODO_TOKEN = "your-token"          # PowerShell, this session only

Run
---
    python zenodo/upload_to_zenodo.py 1234567
    python zenodo/upload_to_zenodo.py 1234567 --verify-only
    python zenodo/upload_to_zenodo.py 1234567 --sandbox     # test against sandbox

The script never publishes. Publishing stays a deliberate click in the browser,
because files can only be changed for 45 days afterwards.
"""

import argparse
import hashlib
import os
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
DESCRIPTORS = REPO_ROOT / "05_output" / "descriptors"
ZENODO_DIR = REPO_ROOT / "zenodo"

RETRIES = 4
TIMEOUT = (30, 1800)      # connect, read. Large files need a long read timeout.


def deposit_files() -> list:
    """The 27 files of the deposit: the meshes, their textures, the paperwork.

    Feature-highlight PNGs are deliberately absent. They are pipeline output
    derived from provisional labels, regenerable from the records, and archiving
    them would give those labels a permanence the evaluation does not support.
    """
    files = sorted(DESCRIPTORS.glob("FRAG-*.glb"))
    files += sorted(DESCRIPTORS.glob("FRAG-*_texture.png"))
    files += [ZENODO_DIR / n for n in ("README.md", "MANIFEST.md", "checksums.sha256")]
    missing = [f for f in files if not f.exists()]
    if missing:
        raise SystemExit("\n  missing:\n" + "\n".join(f"    {m}" for m in missing) + "\n")
    return files


def md5_of(path: Path) -> str:
    """Zenodo reports md5, so compare in its terms rather than our sha256."""
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("record_id", help="the draft's id, from its URL")
    ap.add_argument("--sandbox", action="store_true", help="use sandbox.zenodo.org")
    ap.add_argument("--verify-only", action="store_true",
                    help="check what is already uploaded, send nothing")
    args = ap.parse_args()

    token = os.environ.get("ZENODO_TOKEN", "").strip()
    if not token:
        raise SystemExit("\n  ZENODO_TOKEN is not set. See the header of this file.\n")

    base = "https://sandbox.zenodo.org" if args.sandbox else "https://zenodo.org"
    auth = {"Authorization": f"Bearer {token}"}
    files = deposit_files()
    total = sum(f.stat().st_size for f in files)
    print(f"\n  {len(files)} files, {total/1e9:.2f} GB -> {base} record {args.record_id}\n")

    r = requests.get(f"{base}/api/deposit/depositions/{args.record_id}",
                     headers=auth, timeout=TIMEOUT)
    if r.status_code != 200:
        raise SystemExit(f"\n  cannot read draft {args.record_id}: "
                         f"{r.status_code} {r.text[:200]}\n")
    dep = r.json()
    bucket = dep["links"]["bucket"]

    have = {f["filename"]: f.get("checksum", "").replace("md5:", "")
            for f in dep.get("files", [])}

    ok = bad = sent = 0
    for i, path in enumerate(files, 1):
        mb = path.stat().st_size / 1e6
        local = md5_of(path)

        if path.name in have:
            if have[path.name] == local:
                print(f"  [{i:2}/{len(files)}] {path.name:<34} {mb:8.1f} MB  already there, matches")
                ok += 1
            else:
                print(f"  [{i:2}/{len(files)}] {path.name:<34} {mb:8.1f} MB  ON ZENODO BUT DIFFERENT")
                bad += 1
            continue

        if args.verify_only:
            print(f"  [{i:2}/{len(files)}] {path.name:<34} {mb:8.1f} MB  not uploaded")
            continue

        for attempt in range(1, RETRIES + 1):
            t0 = time.time()
            try:
                with open(path, "rb") as fh:
                    resp = requests.put(f"{bucket}/{path.name}", data=fh,
                                        headers=auth, timeout=TIMEOUT)
                if resp.status_code in (200, 201):
                    remote = resp.json().get("checksum", "").replace("md5:", "")
                    dt = time.time() - t0
                    mark = "verified" if remote == local else "CHECKSUM MISMATCH"
                    print(f"  [{i:2}/{len(files)}] {path.name:<34} {mb:8.1f} MB  "
                          f"{dt:5.0f}s  {mb/max(dt,1e-9):5.1f} MB/s  {mark}")
                    ok += 1 if remote == local else 0
                    bad += 0 if remote == local else 1
                    sent += 1
                    break
                raise RuntimeError(f"{resp.status_code} {resp.text[:160]}")
            except Exception as e:                      # noqa: BLE001
                wait = 2 ** attempt
                if attempt == RETRIES:
                    print(f"  [{i:2}/{len(files)}] {path.name:<34} {mb:8.1f} MB  FAILED: {e}")
                    bad += 1
                else:
                    print(f"      attempt {attempt} failed ({e}); retrying in {wait}s")
                    time.sleep(wait)

    print(f"\n  {ok} present and verified, {bad} problem(s), {sent} sent this run")
    if bad == 0 and ok == len(files):
        print("  All files are on Zenodo and match. Publish from the browser when ready.\n")
    else:
        print("  Re-run this command to continue; it skips what is already correct.\n")


if __name__ == "__main__":
    main()
