"""
AI provayderlar uchun abstract adapter interfeysi.
Har bir yangi provayder qoshish uchun BaseAIAdapter'dan voris olish yetarli.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AIResponse:
    """AI javobi uchun universal format"""
    text: str = ''
    tokens_used: int = 0
    model_used: str = ''
    error: str = ''


class BaseAIAdapter(ABC):
    """Barcha AI provayder adapterlari uchun asosiy klass"""

    def __init__(self, api_key: str, model: str, base_url: str = '', extra_config: dict | None = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.extra_config = extra_config or {}

    @abstractmethod
    def generate_reply(self, system_prompt: str, user_message: str,
                       context: list[dict] | None = None) -> AIResponse:
        """
        AI'dan javob olish.

        Args:
            system_prompt: Tizim prompti (agent sozlamasidan)
            user_message: Foydalanuvchi xabari
            context: Oldingi xabarlar tarixi (ixtiyoriy)

        Returns:
            AIResponse obyekti
        """
        ...

    @abstractmethod
    def validate_credential(self) -> bool:
        """API kalit haqiqiyligini tekshirish"""
        ...
