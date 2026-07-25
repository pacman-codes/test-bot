import pytest
from pydantic import ValidationError

from bot.config import Settings


def test_settings_parse_admins_and_username() -> None:
    settings = Settings(
        bot_token="token",
        private_channel_id=-100123,
        admin_ids="123, 456",
        support_username="@support",
        subscription_price_stars=250,
        _env_file=None,
    )

    assert settings.admin_ids == frozenset({123, 456})
    assert settings.support_username == "support"
    assert settings.subscription_price_stars == 250


@pytest.mark.parametrize("price", [0, 10_001])
def test_settings_reject_invalid_price(price: int) -> None:
    with pytest.raises(ValidationError):
        Settings(
            bot_token="token",
            private_channel_id=-100123,
            subscription_price_stars=price,
            _env_file=None,
        )
