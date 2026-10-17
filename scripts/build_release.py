"""Build a credential-free Windows portable release from a strict allowlist.

Official Python embed ZIP and Pillow wheel must already be in package-cache,
with their publisher SHA-256 values recorded in dependencies.json.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".tavern/package-cache"
OUTPUT = ROOT / ".tavern/releases"
VERSION = "2026.10.18"
FILENAME = "wangxiang-qiatan-20261018-windows-x64.zip"

GUIDE = """妄想洽谈中 Windows 64 位便携版 · 2026.10.18

启动
1. 将整个压缩包解压到可写文件夹，不要在压缩软件内直接运行。
2. 双击“启动妄想洽谈中.cmd”，浏览器会打开 http://127.0.0.1:8765/。
3. 保持启动窗口运行；在窗口按 Ctrl+C 可停止本机服务。

内置 Python 3.15.0 和 Pillow 12.3.0，不必另装 Python 或 Node.js。
本包面向 Windows 10/11 x64。Python 及 Pillow 的许可证分别保留在
runtime/LICENSE.txt 与 runtime/Lib/site-packages/pillow-12.3.0.dist-info/licenses/。

连接自己的模型
首次启动会从 .env.example 创建空白凭据配置 .env；可用记事本编辑。
DeepSeek / Gemini / Grok：填写自己的 API Key；DeepSeek 默认 V4 Pro。
如果本机已有相应 Codex MCP 连接，程序会优先复用。也可参考 integrations
中的连接脚本，用自己的账号配置；包里没有任何人的加密凭据。
GPT、识图、生图和联网查询：另行安装可用的 Codex CLI，并使用自己的
ChatGPT 账号登录。当前已验证 CLI 0.162.1；Codex 登录不随本包转移。
未配置模型时仍可打开界面；在“模型连接”中配置后刷新即可。

使用
含当前九个房间，可以选择参与角色和对应模型，并维护已支持角色的补充设定。
全部房间支持悄悄话，按当前角色名单选择在场者；未在场角色不会读取私谈。
对白优先、简短动作和自然接话规则适用于全部房间，并保留原有角色设定。
各角色同时基于本轮已有对话生成回应，完成后排队随机停顿 1.2 至 2.8 秒再逐条显示。
暂停、发送新消息和切换私谈会取消尚未发表的回复。
往生堂房间包含七位角色、同时回应；该房间的新对话仅在当前浏览器可见。
角色资料位于 resources/wangsheng；七位角色使用包内原人物插画。
往生堂默认由用户扮演荧，使用荧的头像，不另外生成 AI 荧。
铃（兼容输入“玲”）可在全部房间邀请入座，简短自然参与，默认不入座。
“你的参与方式”支持自己聊天、扮演角色、描述场景；用户扮演铃时关闭同名 AI。
身份切换停止旧回复并隔离上下文，历史消息保留原作者；悄悄话保持知情边界。
荧与铃的问答、视觉参考和可移植 skill 位于 resources/protagonists。
铃的立绘已换成透明 PNG，Q 版头像与其他房间的最新素材一并打包。
本机“兼容接口”可配置独立 custom 模型连接，密钥不会随便携包转移。
会话支持自动/深度思考与自动/每次/关闭联网。遇到不确定名词先查资料，
查不到可靠出处时说明尚未核实。图片、聊天和设定修改保存在本目录 .tavern。
妄想天使组合内置基础性格、外观摘要和立绘；完整本机参考 skill 是可选增强。

外网访问
双击“开启外网访问.cmd”，首次会下载并校验 cloudflared。
此电脑需保持运行并联网；每次启动可能得到新地址。
访问密码由本机重新生成，保存在 .tavern/remote/password.txt。
双击“关闭外网访问.cmd”关闭外网入口。

分发内容
包含程序代码、当前界面素材和内置运行时，不包含 API Key、Codex 登录、
原电脑密码、聊天记录、上传/生成的私人图片或用户后续修改的角色档案。
界面角色图片含用户提供及生成的插画；本包不额外授予图片第三方权利。
升级时备份并保留自己原目录的 .env 与 .tavern，不要覆盖个人数据。

自检
双击“检查运行环境.cmd”可检查运行时、图像依赖与程序模块能否加载。
依赖下载来源与校验值见 DEPENDENCIES.json；文件清单见 FILES.json。
"""


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def extract_checked(path, directory):
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            relative = PurePosixPath(item.filename)
            if relative.is_absolute() or ".." in relative.parts or ":" in item.filename or "\\" in item.filename:
                raise ValueError("Unsafe dependency archive member")
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Dependency archive symlink rejected")
        archive.extractall(directory)


def build():
    dependencies = json.loads((CACHE / "dependencies.json").read_text(encoding="utf-8"))
    for item in dependencies.values():
        assert Path(item["filename"]).name == item["filename"]
        assert digest(CACHE / item["filename"]) == item["sha256"], "Dependency checksum mismatch"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="release-build-", dir=ROOT / ".tavern") as temporary:
        target = Path(temporary) / "wangxiang-qiatan"
        target.mkdir()
        paths = [ROOT / name for name in ("app.py", "remote.py", "requirements.txt", ".env.example", "模型选项.json")]
        paths.extend((ROOT / "backend").glob("*.py"))
        paths.append(ROOT / "backend/web-knowledge.schema.json")
        for identifier in ("lumine", "belle"):
            paths.extend(ROOT / "web/assets" / f"protagonist-{identifier}-{kind}.png" for kind in ("stand", "avatar"))
            paths.extend(path for path in (ROOT / "resources/protagonists" / identifier).rglob("*")
                         if path.is_file() and path.suffix in (".md", ".json", ".png"))
        paths.extend(ROOT / "web" / name for name in ("app.js", "index.html", "styles.css", "tea-theme.css", "studio-theme.css", "yunkui-theme.css", "obol-theme.css", "mockingbird-theme.css", "mockingbird-icons.js", "favicon.svg"))
        for character in ("vivian", "hugo"):
            paths.extend(ROOT / "web/assets" / ("mockingbird-" + character + suffix) for suffix in ("-stand.png", "-avatar.png"))
            paths.extend(ROOT / "resources/mockingbird" / folder / (character + ".md") for folder in ("characters", "visual"))
        paths.append(ROOT / "resources/mockingbird/references/assets.json")
        paths.append(ROOT / "resources/mockingbird/references/sources.md")
        for provider in ("deepseek", "gemini", "gpt", "grok"):
            paths.extend(ROOT / "web/assets" / (provider + suffix) for suffix in ("-original.jpg", "-avatar-reference.png"))
        for character in ("sunna", "nangong-yu", "aria"):
            paths.extend(ROOT / "web/assets" / ("zzz-" + character + suffix) for suffix in ("-stand.png", "-avatar.png"))
        for character in ("dialyn", "zhao", "phoenix", "banyue", "promeia"):
            paths.extend(ROOT / "web/assets" / ("krampus-" + character + suffix) for suffix in ("-stand.png", "-avatar.png"))
            paths.extend(ROOT / "resources/krampus" / folder / (character + ".md") for folder in ("characters", "visual"))
        paths.extend(ROOT / "resources/krampus/references" / name for name in ("sources.md", "assets.json"))
        for character in ("yixuan", "ye-shunguang", "pan-yinhu", "ju-fufu"):
            paths.extend(ROOT / "web/assets" / ("yunkui-" + character + suffix) for suffix in ("-stand.png", "-avatar.png"))
            paths.extend(ROOT / "resources/yunkui" / folder / (character + ".md") for folder in ("characters", "visual"))
        paths.append(ROOT / "resources/yunkui/references/assets.json")
        paths.append(ROOT / "resources/yunkui/references/sources.md")
        for character in ("seed", "magus", "orphie", "trigger", "soldier11", "silver-anby"):
            paths.extend(ROOT / "web/assets" / ("obol-" + character + suffix) for suffix in ("-stand.png", "-avatar.png"))
            paths.extend(ROOT / "resources/obol" / folder / (character + ".md") for folder in ("characters", "visual"))
        paths.append(ROOT / "resources/obol/references/assets.json")
        paths.extend(ROOT / "resources/obol/references" / name for name in ("sources.md", "design.md"))
        for group, characters in (("roscaelifer", ("norma", "velina", "sigrid", "claret", "roxy", "lindverne")), ("outer-ring", ("burnice", "caesar", "lucy", "lighter", "pulchra", "piper")),):
            paths.extend(ROOT / "web" / (group + suffix) for suffix in ("-theme.css", "-icons.js"))
            for character in characters:
                paths.extend(ROOT / "web/assets" / (group + "-" + character + suffix) for suffix in ("-stand.png", "-avatar.png"))
                paths.extend(ROOT / "resources" / group / folder / (character + ".md") for folder in ("characters", "visual"))
            paths.append(ROOT / "resources" / group / "references/assets.json")
            paths.append(ROOT / "resources" / group / "references/sources.md")
            paths.append(ROOT / "resources" / group / "references/design.md")
        paths.append(ROOT / "resources/roscaelifer/references/lindverne-model-full.png")
        paths.append(ROOT / "web/assets/user-avatar.png")
        paths.append(ROOT / "web/assets/tea-party-reference.jpg")
        for slot in ("deepseek", "gemini", "gpt"):
            paths.extend(ROOT / "web/assets" / ("wangsheng-" + slot + suffix)
                         for suffix in ("-stand.png", "-avatar.png", ".svg"))
        for slot in ("paimon", "xiangling", "xiao", "zibai"):
            paths.extend(ROOT / "web/assets" / ("wangsheng-" + slot + suffix) for suffix in (".png", ".svg"))
        paths.append(ROOT / "web/assets/wangsheng-room.png")
        for slot in ("deepseek", "gemini", "gpt", "paimon", "xiangling", "xiao", "zibai"):
            paths.extend(ROOT / "resources/wangsheng" / folder / (slot + ".md") for folder in ("characters", "visual"))
        paths.extend(ROOT / "resources/wangsheng" / name for name in (
            "README.md", "relationships.md", "lore/逐月节7.1资料.md", "lore/胡桃神之眼专题.md",
            "references/来源与范围.md", "references/原作人格参考.md", "references/往生堂记忆库.md",
            "references/往生堂记忆库.json", "references/称呼与敬意关系锁定.json", "references/联网来源索引.json"))
        paths.extend(ROOT / "integrations" / provider / (provider + "-mcp.ps1") for provider in ("deepseek", "gemini", "grok"))
        for source in paths:
            assert source.is_file() and not source.is_symlink(), source.name
            relative = source.relative_to(ROOT)
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        example = target / ".env.example"
        example.write_text(example.read_text(encoding="utf-8").replace("# DEEPSEEK_MODEL=deepseek-v4-pro", "DEEPSEEK_MODEL=deepseek-v4-pro"), encoding="utf-8")
        runtime = target / "runtime"
        runtime.mkdir()
        extract_checked(CACHE / dependencies["python"]["filename"], runtime)
        extract_checked(CACHE / dependencies["pillow"]["filename"], runtime / "Lib/site-packages")
        (runtime / "python315._pth").write_text("python315.zip\n.\n..\nLib/site-packages\nimport site\n", encoding="ascii")
        launchers = {
            "启动妄想洽谈中.cmd": ('if not exist ".env" copy ".env.example" ".env" >nul\n'
                                 '"%~dp0runtime\\python.exe" -B "%~dp0app.py" --open\nif errorlevel 1 pause'),
            "开启外网访问.cmd": ('if not exist ".env" copy ".env.example" ".env" >nul\n'
                                '"%~dp0runtime\\python.exe" -B "%~dp0remote.py" start --open\npause'),
            "关闭外网访问.cmd": '"%~dp0runtime\\python.exe" -B "%~dp0remote.py" stop\npause',
            "检查运行环境.cmd": ('"%~dp0runtime\\python.exe" -B -c "import sys,PIL,app; print(\'Python\',sys.version); print(\'Pillow\',PIL.__version__); print(\'Application imports OK\')"\npause'),
        }
        for name, body in launchers.items():
            script = '@echo off\nchcp 65001 >nul\ncd /d "%~dp0"\n' + body + "\n"
            (target / name).write_bytes(script.replace("\n", "\r\n").encode("utf-8"))
        (target / "运行说明.txt").write_text(GUIDE, encoding="utf-8-sig")
        (target / "DEPENDENCIES.json").write_text(json.dumps(dependencies, ensure_ascii=False, indent=2), encoding="utf-8")
        files = []
        forbidden = {".env", ".tavern", ".git", "credential.xml", "password.txt", "conversations.json", "__pycache__"}
        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(target)
            assert not forbidden.intersection(relative.parts), relative
            if relative.parts[0] != "runtime" and path.suffix.lower() in (".py", ".ps1", ".js", ".json", ".txt", ".cmd", ".example", ".md"):
                content = path.read_text(encoding="utf-8-sig")
                assert not re.search(r"(?:xai-|sk-)[A-Za-z0-9_-]{24,}|C:[/\\]Users[/\\]misak", content), "Potential private content in " + str(relative)
            files.append({"path": relative.as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)})
        (target / "FILES.json").write_text(json.dumps({"version": VERSION, "createdAt": datetime.now(timezone.utc).isoformat(), "files": files}, ensure_ascii=False, indent=2), encoding="utf-8")
        pending = OUTPUT / (FILENAME + ".tmp")
        with zipfile.ZipFile(pending, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(target.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(target.parent).as_posix())
        with zipfile.ZipFile(pending) as archive:
            assert archive.testzip() is None
        final = OUTPUT / FILENAME
        pending.replace(final)
        manifest = {"filename": FILENAME, "version": VERSION, "size": final.stat().st_size, "sha256": digest(final)}
        manifest_path = OUTPUT / "latest.json.tmp"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        manifest_path.replace(OUTPUT / "latest.json")
        (OUTPUT / (FILENAME + ".sha256")).write_text(manifest["sha256"] + "  " + FILENAME + "\n", encoding="ascii")
        print(json.dumps({**manifest, "files": len(files) + 1, "privateFilesIncluded": False}, ensure_ascii=False))


if __name__ == "__main__":
    build()
