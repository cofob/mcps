from collections import deque

from mcps_workspace.models import SecretStoreKind, ServiceKind
from mcps_workspace.prompts import EMAIL_PRESETS, PromptIO, collect_profile


class FakePrompt(PromptIO):
    def __init__(self, answers: list[str | bool]) -> None:
        self.answers = deque(answers)
        self.secret_questions: list[str] = []
        self.messages: list[str] = []

    def text(self, message: str, *, default: str = "", secret: bool = False) -> str:
        del default
        if secret:
            self.secret_questions.append(message)
        answer = self.answers.popleft()
        assert isinstance(answer, str)
        return answer

    def confirm(self, message: str, *, default: bool = False) -> bool:
        del message, default
        answer = self.answers.popleft()
        assert isinstance(answer, bool)
        return answer

    def select(self, message: str, choices: list[tuple[str, str]]) -> str:
        del message, choices
        answer = self.answers.popleft()
        assert isinstance(answer, str)
        return answer

    def checkbox(self, message: str, choices: list[tuple[str, str]]) -> list[str]:
        del message, choices
        raise AssertionError("checkbox was not expected")

    def message(self, text: str) -> None:
        self.messages.append(text)


def test_email_presets_are_tls_only() -> None:
    assert EMAIL_PRESETS["gmail"].imap_port == 993
    assert EMAIL_PRESETS["gmail"].smtp_tls == "starttls"
    assert EMAIL_PRESETS["fastmail"].smtp_port == 465
    assert all(preset.imap_tls in {"implicit", "starttls"} for preset in EMAIL_PRESETS.values())


def test_collect_email_profile_masks_credentials() -> None:
    prompt = FakePrompt(
        [
            "personal",
            "gmail",
            "alice@gmail.com",
            "alice@gmail.com",
            "app-password",
            "Alice",
            False,
            False,
            False,
        ]
    )

    collected = collect_profile(
        prompt,
        ServiceKind.EMAIL,
        SecretStoreKind.KEYRING,
        profile_name="mail",
    )

    assert collected.record.server_name == "mcps-email-mail"
    assert collected.record.environment == {}
    assert set(collected.secret_values) == {"EMAIL_ACCOUNTS"}
    assert "app-password" in collected.secret_values["EMAIL_ACCOUNTS"]
    assert prompt.secret_questions == ["IMAP password or app password"]


def test_collect_filesystem_profile_expands_user_path() -> None:
    prompt = FakePrompt(["~/Documents"])

    collected = collect_profile(
        prompt,
        ServiceKind.FILESYSTEM,
        SecretStoreKind.FILE,
        profile_name="docs",
    )

    assert collected.record.name == "docs"
    assert collected.record.environment["FILESYSTEM_ROOT_DIR"].endswith("/Documents")
