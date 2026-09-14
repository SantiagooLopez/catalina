import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalRuntimePolicy:
    timeout_seconds: float = 120.0
    max_concurrent: int = 1

    def __post_init__(self) -> None:
        if (
            type(self.timeout_seconds) not in (int, float)
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds debe ser un número finito positivo.")

        if type(self.max_concurrent) is not int or self.max_concurrent < 1:
            raise ValueError("max_concurrent debe ser un entero positivo.")


class RetrievalExecutionError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        request_id: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.request_id = request_id
