import subprocess

import pytest

from src.services import state_sync
from src.services.state_sync import GitStateSync


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def data_repo(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    work = tmp_path / "data"
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True, capture_output=True)
    git(work, "config", "user.email", "t@example.com")
    git(work, "config", "user.name", "t")
    (work / "app_state.json").write_text("{}\n")
    (work / "other.txt").write_text("x\n")
    git(work, "add", "app_state.json")
    git(work, "commit", "-qm", "init")
    git(work, "push", "-qu", "origin", "main")
    return work


def test_disabled_unless_state_path_is_explicit(data_repo):
    assert not GitStateSync(str(data_repo / "app_state.json"), explicit=False).repo


def test_refuses_the_code_repo():
    assert not GitStateSync(state_sync.CODE_REPO + "/src/web/app_state.json", explicit=True).repo


def test_commits_only_the_state_file_and_pushes(data_repo):
    git(data_repo, "add", "other.txt")                      # someone else's staged change
    sync = GitStateSync(str(data_repo / "app_state.json"), explicit=True)
    (data_repo / "app_state.json").write_text('{"x": 1}\n')
    sync._commit_and_push()
    assert git(data_repo, "show", "--name-only", "--format=", "HEAD").split() == ["app_state.json"]
    assert "A  other.txt" in git(data_repo, "status", "--porcelain")
    assert git(data_repo, "rev-list", "--count", "@{upstream}..HEAD").strip() == "0"
    assert sync.status["state"] == "ok"


def test_retries_push_of_existing_ahead_commit(data_repo, monkeypatch):
    sync = GitStateSync(str(data_repo / "app_state.json"), explicit=True)
    (data_repo / "app_state.json").write_text('{"x": 2}\n')
    real = state_sync._git
    monkeypatch.setattr(state_sync, "_git", lambda repo, *a, **k: subprocess.CompletedProcess(a, 1, "", "offline") if a[0] == "push" else real(repo, *a, **k))
    sync._commit_and_push()
    assert sync.status["state"] == "push_failed"
    monkeypatch.setattr(state_sync, "_git", real)
    sync._commit_and_push()                                  # no new change, but still ahead
    assert git(data_repo, "rev-list", "--count", "@{upstream}..HEAD").strip() == "0"
    assert sync.status["state"] == "ok"


def test_failed_pull_marks_state_untrusted(data_repo, monkeypatch):
    sync = GitStateSync(str(data_repo / "app_state.json"), explicit=True)
    monkeypatch.setattr(state_sync, "_git", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "diverged"))
    sync.pull()
    assert not sync.trusted and sync.status["state"] == "pull_failed"
