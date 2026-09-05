from dataclasses import dataclass


@dataclass(slots=True)
class AppError(Exception):
    code: str
    title: str
    detail: str
    status_code: int = 400
    retryable: bool = False
    action: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def not_found(resource: str) -> AppError:
    return AppError("NOT_FOUND", "Not found", f"{resource} does not exist.", 404)
