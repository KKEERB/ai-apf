"""Exercise the documented native-shell installation without network access.

Each run substitutes a fresh synthetic user directory in the README snippet and
stubs `git clone`; all source content is copied from the current checkout.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
README = (ROOT / "README.md").read_text(encoding="utf-8")
SKILL = ROOT / "skills" / "ai-apf"
MARKER = b"keep this existing file\n"


def install_snippet(language):
    start = README.index("```" + language + "\n") + len("```" + language + "\n")
    return README[start:README.index("\n```", start)]


def snapshot(directory):
    return {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()}


def command_for(clone_succeeds):
    if os.name == "nt":
        script = install_snippet("powershell")
        script = script.replace("$env:CODEX_HOME", "$env:APF_TEST_CODEX_HOME")
        script = script.replace("$HOME", "$env:APF_TEST_HOME")
        stub = "function git { $global:LASTEXITCODE = " + ("0" if clone_succeeds else "1") + " }\n"
        return ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", stub + script]
    script = install_snippet("bash")
    script = script.replace("${CODEX_HOME:-$HOME/.codex}", "${APF_TEST_CODEX_HOME}")
    script = script.replace("$HOME", "${APF_TEST_HOME}")
    stub = "git() { return " + ("0" if clone_succeeds else "1") + "; }\n"
    return ["bash", "-eu", "-c", stub + script]


def main():
    with tempfile.TemporaryDirectory(prefix="ai-apf 安装 test ") as directory:
        root = Path(directory)
        work = root / "work 空格"
        home = root / "用户 home"
        codex = root / "自定义 codex home"
        work.mkdir()
        home.mkdir()
        source = work / "ai-apf" / "skills" / "ai-apf"
        source.parent.mkdir(parents=True)
        shutil.copytree(SKILL, source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        source_snapshot = snapshot(source)
        destination = home / ".agents" / "skills" / "ai-apf"
        env = dict(os.environ, APF_TEST_HOME=str(home), APF_TEST_CODEX_HOME=str(codex))

        def run(clone_succeeds=True):
            return subprocess.run(command_for(clone_succeeds), cwd=work, env=env,
                                  capture_output=True, text=True, encoding="utf-8")

        failed_clone = run(False)
        assert failed_clone.returncode != 0, failed_clone.stdout
        assert not destination.exists(), "A failed clone must not install anything."

        first = run()
        assert first.returncode == 0, first.stdout + first.stderr
        assert snapshot(destination) == source_snapshot, "Installed files differ from the repository."
        (destination / "existing-marker.txt").write_bytes(MARKER)
        second = run()
        assert second.returncode == 0, second.stdout + second.stderr
        assert "already exists" in second.stdout, second.stdout
        assert (destination / "existing-marker.txt").read_bytes() == MARKER

        shutil.rmtree(destination)
        other = codex / "skills" / "ai-apf"
        other.mkdir(parents=True)
        (other / "existing-marker.txt").write_bytes(MARKER)
        third = run()
        assert third.returncode == 0, third.stdout + third.stderr
        assert "already exists" in third.stdout, third.stdout
        assert not destination.exists(), "A duplicate in CODEX_HOME must block installation."
        assert (other / "existing-marker.txt").read_bytes() == MARKER

    print("Documented native-shell install: passed (Unicode/space paths, clone failure, duplicates).")


if __name__ == "__main__":
    main()
