"""Unpack the actual distribution and launch it without system Python or accounts."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".tavern"
RELEASES = WORK / "releases"


def check():
    metadata = json.loads((RELEASES / "latest.json").read_text(encoding="utf-8"))
    archive_path = RELEASES / metadata["filename"]
    with archive_path.open("rb") as handle:
        assert hashlib.file_digest(handle, "sha256").hexdigest() == metadata["sha256"]
    with tempfile.TemporaryDirectory(prefix="release-check-", dir=WORK) as temporary:
        folder = Path(temporary).resolve()
        assert folder.is_relative_to(WORK.resolve())
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            assert not any(part in {".env", ".tavern", "credential.xml", "password.txt", "conversations.json"}
                           for name in names for part in Path(name).parts)
            archive.extractall(folder)
        application = folder / "wangxiang-qiatan"
        runtime = application / "runtime/python.exe"
        records = json.loads((application / "FILES.json").read_text(encoding="utf-8"))["files"]
        for record in records:
            with (application / record["path"]).open("rb") as handle:
                assert hashlib.file_digest(handle, "sha256").hexdigest() == record["sha256"]
        env = dict(os.environ)
        for name in ("DEEPSEEK_API_KEY", "GEMINI_API_KEY", "GROK_API_KEY", "XAI_API_KEY", "CODEX_CLI_PATH"):
            env.pop(name, None)
        env.update({"CODEX_HOME": str(folder / "empty-codex"), "LOCALAPPDATA": str(folder / "empty-local"),
                    "PATH": "", "PYTHONIOENCODING": "utf-8"})
        result = subprocess.run([str(runtime), "-B", "-c", "import PIL,app; print(PIL.__version__)"],
                                cwd=application, env=env, capture_output=True, text=True, encoding="utf-8", timeout=20)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "12.3.0"
        log_path = folder / "launch.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen([str(runtime), "-B", "-u", "app.py", "--port", "0"],
                                       cwd=application, env=env, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                deadline = time.monotonic() + 20
                address = None
                while time.monotonic() < deadline:
                    text = log_path.read_text(encoding="utf-8", errors="replace")
                    match = re.search(r"http://127\.0\.0\.1:\d+", text)
                    if match:
                        address = match.group()
                        break
                    if process.poll() is not None:
                        raise RuntimeError("Packaged application failed: " + text[:1000])
                    threading.Event().wait(0.1)
                assert address, "Packaged application did not become ready"
                with urllib.request.urlopen(address + "/api/bootstrap", timeout=5) as response:
                    bootstrap = json.load(response)
                assert bootstrap["conversations"] == []
                assert not any(p["configured"] for p in bootstrap["providers"])
                assert {r["id"] for r in bootstrap["rooms"]} == {"standard", "zzz-trio", "wangsheng-trio", "zzz-krampus", "zzz-yunkui", "zzz-obol", "zzz-mockingbird", "zzz-outer-ring", "zzz-roscaelifer"}
                routes = {"/roscaelifer-theme.css", "/roscaelifer-icons.js", "/outer-ring-theme.css", "/outer-ring-icons.js", "/", "/app.js", "/styles.css", "/tea-theme.css", "/studio-theme.css", "/yunkui-theme.css", "/obol-theme.css", "/mockingbird-theme.css", "/mockingbird-icons.js", "/favicon.svg",
                          "/assets/user-avatar.png", "/assets/tea-party-reference.jpg"}
                for room in bootstrap["rooms"]:
                    for character in room["characters"].values():
                        routes.update(route for route in (character["stand"], character["avatar"]) if route)
                    if room.get("background"):
                        routes.add(room["background"])
                for route in routes:
                    with urllib.request.urlopen(address + route, timeout=5) as response:
                        assert response.status == 200 and response.read(1)
                output = {"ok": True, "version": metadata["version"], "sha256": metadata["sha256"],
                          "archiveBytes": metadata["size"], "filesVerified": len(records),
                          "routesVerified": len(routes), "systemPythonRequired": False,
                          "pillow": result.stdout.strip(), "privateDataAbsent": True,
                          "unconfiguredNewMachineStarts": True}
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
        (RELEASES / "verification.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    check()
