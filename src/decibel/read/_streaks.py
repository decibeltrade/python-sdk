from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ._base import BaseReader

__all__ = [
    "AccountStreaks",
    "StreaksReader",
]


class AccountStreaks(BaseModel):
    # The streaks endpoint is the one points route that serves camelCase keys; the aliases keep
    # the SDK surface snake_case like every other model.
    model_config = ConfigDict(populate_by_name=True)

    owner: str
    current_streak: int = Field(alias="currentStreak")
    streak_ipoints: float = Field(alias="streakIpoints")
    streak_amps_estimate: float = Field(alias="streakAmpsEstimate")
    grace_days_available: int = Field(alias="graceDaysAvailable")
    grace_days_used: int = Field(alias="graceDaysUsed")
    qualifying_dates: list[str] = Field(alias="qualifyingDates")


class StreaksReader(BaseReader):
    async def get_by_owner(self, owner_addr: str) -> AccountStreaks:
        """Streak data for an owner, including qualifying dates and grace-day usage."""
        response, _, _ = await self.get_request(
            model=AccountStreaks,
            url=f"{self.config.trading_http_url}/api/v1/streaks/account",
            params={"owner": owner_addr},
        )
        return response
