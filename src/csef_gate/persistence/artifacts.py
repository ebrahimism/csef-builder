"""Bounded immutable content storage, independently rehashed on every read."""
from __future__ import annotations

import os
from pathlib import Path
import re
import time

from ..core import Refused, digest, encoded, plain, relative_name
from .events import ensure_runtime
from .sqlite import DATABASE, connection


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = Path(root).absolute()
        self.db = self.root / DATABASE
        ensure_runtime(self.db)

    def _path(self, sha):
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise Refused("invalid content hash")
        path = self.root / "objects" / sha[:2] / sha[2:]
        plain(path)
        return path

    def put(self, content, *, media_type="application/octet-stream", provenance="controller"):
        if type(content) is not bytes or len(content) > 1_000_000:
            raise Refused("artifact must be bounded bytes")
        if any(not isinstance(value, str) or not value.strip() for value in (media_type, provenance)):
            raise Refused("artifact metadata required")
        sha = digest(content)
        path = self._path(sha)
        with connection(self.db) as con:
            con.execute("BEGIN IMMEDIATE")
            registered = con.execute("SELECT bytes FROM stored_artifacts WHERE sha256=?", (sha,)).fetchone()
            if path.exists() != (registered is not None):
                raise Refused("orphan artifact or missing object; inspect before recovery")
            if path.exists():
                if path.stat().st_size != len(content) or digest(path.read_bytes()) != sha:
                    raise Refused("corrupt or incomplete artifact; preserve it for inspection")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
            con.execute("INSERT INTO stored_artifacts VALUES(?,?,?,?,?) ON CONFLICT(sha256) DO NOTHING",
                        (sha, len(content), media_type, provenance, time.time()))
            row = con.execute("SELECT bytes FROM stored_artifacts WHERE sha256=?", (sha,)).fetchone()
            if row[0] != len(content):
                raise Refused("artifact metadata mismatch")
        return {"sha256": sha, "bytes": len(content)}

    def get(self, sha):
        path = self._path(sha)
        with connection(self.db) as con:
            row = con.execute("SELECT bytes FROM stored_artifacts WHERE sha256=?", (sha,)).fetchone()
        if row is None or not path.is_file() or path.stat().st_size != row[0] or row[0] > 1_000_000:
            raise Refused("missing or invalid registered artifact")
        content = path.read_bytes()
        if digest(content) != sha:
            raise Refused("artifact integrity mismatch")
        return content

    def verify(self, manifest):
        if not isinstance(manifest, dict) or not manifest or len({str(k).casefold() for k in manifest}) != len(manifest):
            raise Refused("nonempty noncolliding artifact manifest required")
        content = {}
        for name, item in manifest.items():
            relative_name(name)
            if not isinstance(item, dict) or set(item) != {"sha256", "bytes"} or type(item["bytes"]) is not int:
                raise Refused("invalid artifact manifest entry")
            value = self.get(item["sha256"])
            if len(value) != item["bytes"]:
                raise Refused("artifact size mismatch")
            content[name] = value
        return content

    def export_allowed(self, manifest, destination):
        content = self.verify(manifest)
        destination = Path(destination).absolute()
        plain(destination)
        if destination.exists():
            raise Refused("artifact export destination must be new")
        # Reject file/directory aliasing before any writes.
        names = [n.casefold() for n in content]
        if any(a != b and b.startswith(a + "/") for a in names for b in names):
            raise Refused("artifact path collision")
        destination.mkdir(parents=True)
        for name, value in content.items():
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(value)
        return {"manifest_sha256": digest(encoded(manifest)), "files": len(content)}
