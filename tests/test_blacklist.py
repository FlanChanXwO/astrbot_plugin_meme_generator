import astrbot.core.message.components as Comp
import pytest
from astrbot_plugin_meme_generator.core.meme_manager import MemeManager
from astrbot_plugin_meme_generator.core.param_collector import ParamCollector
from astrbot_plugin_meme_generator.main import MemeConfig


class DummyConfig(dict):
    def save_config(self) -> None:
        pass


class DummyEvent:
    def __init__(self, uid: str, umo: str, messages=None, message_str: str = ""):
        self.uid = uid
        self.unified_msg_origin = umo
        self._messages = messages or []
        self._message_str = message_str

    def get_sender_id(self) -> str:
        return self.uid

    def get_message_str(self) -> str:
        return self._message_str

    def get_messages(self):
        return self._messages

    def get_self_id(self) -> str:
        return "99999"

    def get_sender_name(self) -> str:
        return "sender"


class DummyCooldownManager:
    def is_user_in_cooldown(self, _uid: str) -> bool:
        return False

    def record_user_use(self, _uid: str) -> None:
        raise AssertionError("blacklisted target must not record cooldown usage")


class DummyParams:
    max_images = 1
    min_texts = 0
    max_texts = 0
    default_texts = ()


class DummyMemeInfo:
    params = DummyParams()


class DummyMeme:
    info = DummyMemeInfo()


class DummyTemplateManager:
    async def find_keyword(self, _message_str: str, _prefix: str):
        return "摸头"

    async def find_meme(self, _keyword: str):
        return DummyMeme()


class DummyResourceStatus:
    def get_block_message(self, keyword_matched: bool):
        assert keyword_matched is True


class DummyImageGenerator:
    async def generate_image(self, *_args, **_kwargs):
        return b"generated"


def test_blacklist_matches_uid_and_umo() -> None:
    config = MemeConfig(
        DummyConfig(
            {
                "user_blacklist": [
                    "3085974225",
                    "aiocqhttp:FriendMessage:3085974225",
                ]
            }
        )
    )

    assert config.is_blacklisted(uid="3085974225") is True
    assert config.is_blacklisted(umo="aiocqhttp:FriendMessage:3085974225") is True
    assert (
        config.is_blacklisted(uid="10001", umo="aiocqhttp:GroupMessage:20002") is False
    )


@pytest.mark.asyncio
async def test_generate_meme_silently_ignores_blacklisted_sender_or_umo() -> None:
    manager = MemeManager.__new__(MemeManager)
    manager.config = MemeConfig(
        DummyConfig(
            {
                "user_blacklist": [
                    "3085974225",
                    "aiocqhttp:GroupMessage:20002",
                ]
            }
        )
    )

    assert (
        await manager.generate_meme(
            DummyEvent("3085974225", "aiocqhttp:GroupMessage:10001")
        )
        is None
    )
    assert (
        await manager.generate_meme(DummyEvent("10001", "aiocqhttp:GroupMessage:20002"))
        is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("messages", "message_str"),
    [
        ([Comp.At(qq="3085974225")], "摸头"),
        ([Comp.Plain("摸头 3085974225")], "摸头 3085974225"),
    ],
)
async def test_generate_meme_silently_ignores_blacklisted_avatar_target(
    messages, message_str: str
) -> None:
    manager = MemeManager.__new__(MemeManager)
    manager.config = MemeConfig(DummyConfig({"user_blacklist": ["3085974225"]}))
    manager.cooldown_manager = DummyCooldownManager()
    manager.template_manager = DummyTemplateManager()
    manager.resource_status = DummyResourceStatus()
    manager.param_collector = ParamCollector(network_utils=None, config=manager.config)
    manager.image_generator = DummyImageGenerator()

    result = await manager.generate_meme(
        DummyEvent(
            "10001",
            "aiocqhttp:GroupMessage:20002",
            messages=messages,
            message_str=message_str,
        )
    )

    assert result is None
