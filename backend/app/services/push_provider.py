from dataclasses import dataclass


@dataclass
class PushResult:
    ok: bool
    error: str | None = None


class LogPushProvider:
    """Development provider: logs the payload and reports success.

    Production swaps this for Pushe/Najva/Chabok behind the same interface.
    """

    def send(self, token: str, title: str, body: str) -> PushResult:
        print(f"[push] token={token[:12]}… {title}: {body}")
        return PushResult(ok=True)
