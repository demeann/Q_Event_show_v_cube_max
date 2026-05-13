"""ORM-модели приложения.

Все модели регистрируются здесь, чтобы Alembic видел их в `Base.metadata`
при автогенерации миграций.
"""

from app.db.models.answer import UserAnswer
from app.db.models.audit import EmailValidationLog
from app.db.models.broadcast import (
    Broadcast,
    BroadcastRecipient,
    BroadcastStatus,
    BroadcastTemplate,
    BroadcastTemplateType,
    RecipientStatus,
)
from app.db.models.progress import (
    RoundProgressStatus,
    TopicStatus,
    UserRoundProgress,
    UserTopicProgress,
)
from app.db.models.round import Round, RoundCode, RoundStatus
from app.db.models.round_question import RoundQuestion
from app.db.models.user import User
from app.db.models.winner import Winner, WinnerSelection

__all__ = [
    # Core entities
    "User",
    "Round",
    "RoundCode",
    "RoundStatus",
    "RoundQuestion",
    # Progress
    "UserRoundProgress",
    "UserTopicProgress",
    "RoundProgressStatus",
    "TopicStatus",
    # Answers
    "UserAnswer",
    # Winners
    "WinnerSelection",
    "Winner",
    # Broadcasts
    "BroadcastTemplate",
    "BroadcastTemplateType",
    "Broadcast",
    "BroadcastStatus",
    "BroadcastRecipient",
    "RecipientStatus",
    # Audit
    "EmailValidationLog",
]
