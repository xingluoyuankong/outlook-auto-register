from pathlib import Path

from .. import credential_tools as tools


def test_parse_delimited_four_credential_line():
    parsed = tools.parse_credential_text(
        "user@example.com----Passw0rd!----14d82eec-204b-4c2f-b7e8-296a70dab67e----0.ABC_def-ghi_refresh_token_value_1234567890"
    )

    assert parsed is not None
    assert parsed.email == "user@example.com"
    assert parsed.password == "Passw0rd!"
    assert parsed.client_id == "14d82eec-204b-4c2f-b7e8-296a70dab67e"
    assert parsed.refresh_token == "0.ABC_def-ghi_refresh_token_value_1234567890"


def test_parse_chinese_key_value_credentials():
    parsed = tools.parse_credential_text(
        "\n".join(
            [
                "\u90ae\u7bb1\uff1ahelper@example.com",
                "\u5bc6\u7801\uff1aSecret123!",
                "client_id: 14d82eec-204b-4c2f-b7e8-296a70dab67e",
                "refresh_token: 0.refresh_token-value-12345678901234567890",
            ]
        )
    )

    assert parsed is not None
    assert parsed.email == "helper@example.com"
    assert parsed.password == "Secret123!"
    assert parsed.refresh_token == "0.refresh_token-value-12345678901234567890"


def test_extract_code_from_chinese_and_english_text():
    assert tools.extract_code("\u9a8c\u8bc1\u7801\uff1a123456") == "123456"
    assert tools.extract_code("Your security code is 654321.") == "654321"


def test_pick_auxiliary_mailbox_uses_txt_credentials(tmp_path):
    helper = tmp_path / "helper.txt"
    helper.write_text(
        "helper@example.com----Secret123!----14d82eec-204b-4c2f-b7e8-296a70dab67e----0.refresh_token-value-12345678901234567890\n",
        encoding="utf-8",
    )

    result = tools.pick_auxiliary_mailbox({"auxiliary_dir": str(tmp_path), "seed": "stable"})

    assert result["ok"] is True
    assert result["email"] == "helper@example.com"
    assert Path(result["source_path"]) == helper
