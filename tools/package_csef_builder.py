"""Build a reproducible local marketplace snapshot and a one-root plugin ZIP."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile


def build(root):
    source = root / "plugins/csef-builder"
    manifest = json.loads((source / "plugin.json").read_text(encoding="utf-8"))
    overlay = json.loads((source / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == overlay["name"] == "csef-builder"
    assert manifest["version"] == overlay["version"]
    assert (source / "skills/csef-build/SKILL.md").is_file()
    files = sorted(p for p in source.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    assert all(not p.is_symlink() and p.suffix not in {".pyc", ".pyo"} for p in files)
    output = root / "deliverables"
    market = output / "csef-local"
    destination = market / "plugins/csef-builder"
    # Copy only enumerated package sources, never dependencies or machine config.
    for path in files:
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    catalog = market / ".agents/plugins/marketplace.json"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(json.dumps({"name": "csef-local", "interface": {"displayName": "CSEF Local"},
        "plugins": [{"name": "csef-builder", "source": {"source": "local", "path": "./plugins/csef-builder"},
                     "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                     "category": "Developer Tools"}]}, indent=2) + "\n", encoding="utf-8")
    archive = output / ("csef-builder-" + manifest["version"] + ".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as stream:
        for path in files:
            info = zipfile.ZipInfo("csef-builder/" + path.relative_to(source).as_posix(), (2026, 11, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            stream.writestr(info, path.read_bytes())
    summary = {"name": manifest["name"], "version": manifest["version"], "files": len(files),
               "archive": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
               "marketplace_root": str(market)}
    (output / "csef-builder-package.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(Path(__file__).resolve().parents[1]), indent=2))
