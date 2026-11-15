"""Append a layer with the current sorter/ sources to a `docker save` tarball (no Docker needed).

    python scripts/patch_image.py ~/aalto-img/junction-sorter-v5.tar ~/aalto-img/junction-sorter-v6.tar junction-sorter:v6

Use only when the change is Python files under sorter/ (same dependencies); the Dockerfile's build-time import check
does not run, so run the tests from source first. Verify with `crane validate --tarball <out>`.
"""
import gzip, hashlib, io, json, sys, tarfile, time
from pathlib import Path

src, dst, tag = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
here = Path(__file__).resolve().parent.parent

layer = io.BytesIO()
with tarfile.open(fileobj=layer, mode="w", format=tarfile.PAX_FORMAT) as t:
    for d in ("app", "app/sorter"):
        ti = tarfile.TarInfo(d); ti.type = tarfile.DIRTYPE; ti.mode = 0o755; ti.mtime = int(time.time()); t.addfile(ti)
    for f in sorted((here / "sorter").glob("*.py")):
        data = f.read_bytes()
        ti = tarfile.TarInfo(f"app/sorter/{f.name}"); ti.size = len(data); ti.mode = 0o644; ti.mtime = int(time.time())
        t.addfile(ti, io.BytesIO(data))
layer_bytes = layer.getvalue()
diff_id = "sha256:" + hashlib.sha256(layer_bytes).hexdigest()

with tarfile.open(src) as tin:
    members = {m.name: tin.extractfile(m).read() if m.isfile() else None for m in tin.getmembers()}
manifest = json.loads(members["manifest.json"])
cfg_name = manifest[0]["Config"]
cfg = json.loads(members[cfg_name])
cfg["rootfs"]["diff_ids"].append(diff_id)
cfg.setdefault("history", []).append({"created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                      "created_by": "patch_image.py: COPY sorter /app/sorter"})
cfg_bytes = json.dumps(cfg, separators=(",", ":")).encode()
cfg_id = hashlib.sha256(cfg_bytes).hexdigest()
layer_gz = gzip.compress(layer_bytes, mtime=0)
layer_name = f"blobs/sha256/{hashlib.sha256(layer_gz).hexdigest()}"
manifest[0]["Config"] = f"{cfg_id}.json"
manifest[0]["Layers"].append(layer_name)
manifest[0]["RepoTags"] = [tag]

with tarfile.open(dst, "w") as tout:
    def add(name, data):
        ti = tarfile.TarInfo(name); ti.size = len(data); ti.mode = 0o644; tout.addfile(ti, io.BytesIO(data))
    for name, data in members.items():
        if data is None or name in ("manifest.json", cfg_name, "repositories", "index.json", "oci-layout"):
            continue
        add(name, data)
    add(f"{cfg_id}.json", cfg_bytes)
    add(layer_name, layer_gz)
    add("manifest.json", json.dumps(manifest).encode())
print("image id sha256:" + cfg_id, "new layer", diff_id, f"{len(layer_bytes)} bytes")
