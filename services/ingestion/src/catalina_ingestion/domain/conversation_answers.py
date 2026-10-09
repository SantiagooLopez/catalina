from dataclasses import dataclass

from catalina_ingestion.domain.conversations import (
    Message,
)
from catalina_ingestion.domain.generation import (
    GeneratedAnswer,
)


@dataclass(frozen=True, slots=True)
class ConversationAnswerResult:
    answer: GeneratedAnswer
    message: Message
