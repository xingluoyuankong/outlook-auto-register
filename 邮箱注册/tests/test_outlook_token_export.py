from pathlib import Path

from ..outlook_token_export import (
    BUILTIN_CLIENT_ID,
    locate_credential_file,
    matching_credential_files,
    save_created_outlook_account,
)


def test_save_created_outlook_account_waits_for_refresh_token_before_writing_file(tmp_path: Path):
    result = save_created_outlook_account(
        "Example@Outlook.com",
        "SecretPassword!",
        out_dir=tmp_path,
        start_token_job=False,
    )

    assert result["ok"] is True
    assert result["reason"] == "pending_refresh_token"
    assert Path(result["credential_path"]).name == "example@outlook.com.txt"
    assert not Path(result["credential_path"]).exists()


def test_save_created_outlook_account_does_not_spawn_external_token_tool(tmp_path: Path):
    result = save_created_outlook_account(
        "Example@Outlook.com",
        "SecretPassword!",
        out_dir=tmp_path,
        start_token_job=True,
    )

    assert result["ok"] is True
    assert result["reason"] == "pending_refresh_token"
    assert result["token_job"]["status"] == "not_started"
    assert result["token_job"]["reason"] == "plugin_integrated_oauth_only"
    assert not Path(result["credential_path"]).exists()


def test_save_created_outlook_account_refresh_update_does_not_get_erased(tmp_path: Path):
    save_created_outlook_account(
        "example@outlook.com",
        "SecretPassword!",
        out_dir=tmp_path,
        start_token_job=False,
    )
    save_created_outlook_account(
        "example@outlook.com",
        "SecretPassword!",
        refresh_token="refresh-1",
        out_dir=tmp_path,
        start_token_job=False,
    )
    save_created_outlook_account(
        "example@outlook.com",
        "SecretPassword!",
        out_dir=tmp_path,
        start_token_job=False,
    )

    credential_path = tmp_path / "example@outlook.com.txt"
    assert credential_path.read_text(encoding="utf-8") == (
        f"example@outlook.com----SecretPassword!----{BUILTIN_CLIENT_ID}----refresh-1\n"
    )


def test_save_created_outlook_account_writes_single_email_named_credential_file(tmp_path: Path):
    result = save_created_outlook_account(
        "Example@Outlook.com",
        "SecretPassword!",
        access_token="access-1",
        refresh_token="refresh-1",
        expires_in=3599,
        token_type="Bearer",
        scope="offline_access Mail.Read",
        out_dir=tmp_path,
        start_token_job=False,
    )

    assert result["ok"] is True
    credential_path = Path(result["credential_path"])
    assert credential_path.name == "example@outlook.com.txt"
    assert "token_json_path" not in result
    assert "token_env_path" not in result
    assert "token_combo_path" not in result
    assert credential_path.read_text(encoding="utf-8") == (
        f"example@outlook.com----SecretPassword!----{BUILTIN_CLIENT_ID}----refresh-1\n"
    )
    assert "all_credentials_path" not in result
    assert sorted(path.name for path in tmp_path.iterdir()) == ["example@outlook.com.txt"]


def test_save_created_outlook_account_writes_independent_email_named_files(tmp_path: Path):
    save_created_outlook_account(
        "first@outlook.com",
        "SecretPassword1!",
        refresh_token="refresh-1",
        out_dir=tmp_path,
        start_token_job=False,
    )
    save_created_outlook_account(
        "second@hotmail.com",
        "SecretPassword2!",
        refresh_token="refresh-2",
        out_dir=tmp_path,
        start_token_job=False,
    )

    assert (tmp_path / "first@outlook.com.txt").read_text(encoding="utf-8") == (
        f"first@outlook.com----SecretPassword1!----{BUILTIN_CLIENT_ID}----refresh-1\n"
    )
    assert (tmp_path / "second@hotmail.com.txt").read_text(encoding="utf-8") == (
        f"second@hotmail.com----SecretPassword2!----{BUILTIN_CLIENT_ID}----refresh-2\n"
    )


def test_matching_credential_files_includes_download_suffix_variants(tmp_path: Path):
    base = tmp_path / "example@outlook.com.txt"
    suffixed = tmp_path / "example@outlook.com__run01.txt"
    suffixed.write_text("suffix\n", encoding="utf-8")
    base.write_text("base\n", encoding="utf-8")

    matches = matching_credential_files("example@outlook.com", tmp_path)

    assert matches == [base, suffixed]


def test_locate_credential_file_falls_back_to_latest_suffix_when_base_missing(tmp_path: Path):
    older = tmp_path / "example@outlook.com__run01.txt"
    newer = tmp_path / "example@outlook.com__run02.txt"
    older.write_text("older\n", encoding="utf-8")
    newer.write_text("newer\n", encoding="utf-8")

    assert locate_credential_file("example@outlook.com", tmp_path) == newer
