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

    def get_platform_name(self) -> str:
        return "test"


class DummyCooldownManager:
    def is_user_in_cooldown(self, _uid: str) -> bool:
        return False

    def record_user_use(self, _uid: str) -> None:
        raise AssertionError("blacklisted target must not record cooldown usage")


class SuccessfulCooldownManager(DummyCooldownManager):
    def record_user_use(self, _uid: str) -> None:
        pass


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


class TrackingNetworkUtils:
    def __init__(self):
        self.avatar_requests = []

    async def get_avatar(self, uid: str):
        self.avatar_requests.append(uid)
        return b"avatar"


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
async def test_generate_meme_silently_ignores_blacklisted_umo() -> None:
    manager = MemeManager.__new__(MemeManager)
    manager.config = MemeConfig(
        DummyConfig(
            {
                "user_blacklist": [
                    "aiocqhttp:GroupMessage:20002",
                ]
            }
        )
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


@pytest.mark.asyncio
async def test_generate_meme_silently_ignores_blacklisted_reply_sender() -> None:
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
            messages=[
                Comp.Reply(
                    id="123",
                    sender_id="3085974225",
                    sender_nickname="protected",
                    chain=[Comp.Plain("quoted")],
                )
            ],
            message_str="摸头",
        )
    )

    assert result is None


@pytest.mark.asyncio
async def test_protected_user_can_generate_meme_for_another_user() -> None:
    manager = MemeManager.__new__(MemeManager)
    manager.config = MemeConfig(DummyConfig({"user_blacklist": ["3085974225"]}))
    manager.cooldown_manager = SuccessfulCooldownManager()
    manager.template_manager = DummyTemplateManager()
    manager.resource_status = DummyResourceStatus()
    manager.param_collector = ParamCollector(network_utils=None, config=manager.config)
    manager.image_generator = DummyImageGenerator()

    result = await manager.generate_meme(
        DummyEvent(
            "3085974225",
            "aiocqhttp:GroupMessage:20002",
            messages=[Comp.At(qq="10001")],
            message_str="摸头",
        )
    )

    assert result == b"generated"


@pytest.mark.asyncio
async def test_protected_user_avatar_is_not_used_as_default_material() -> None:
    network_utils = TrackingNetworkUtils()
    manager = MemeManager.__new__(MemeManager)
    manager.config = MemeConfig(DummyConfig({"user_blacklist": ["3085974225"]}))
    manager.cooldown_manager = SuccessfulCooldownManager()
    manager.template_manager = DummyTemplateManager()
    manager.resource_status = DummyResourceStatus()
    manager.param_collector = ParamCollector(
        network_utils=network_utils,
        config=manager.config,
    )
    manager.image_generator = DummyImageGenerator()

    result = await manager.generate_meme(
        DummyEvent(
            "3085974225",
            "aiocqhttp:GroupMessage:20002",
            messages=[],
            message_str="摸头",
        )
    )

    assert result == b"generated"
    assert "3085974225" not in network_utils.avatar_requests


@pytest.mark.asyncio
async def test_protected_user_can_use_own_quoted_image() -> None:
    manager = MemeManager.__new__(MemeManager)
    manager.config = MemeConfig(DummyConfig({"user_blacklist": ["3085974225"]}))
    manager.cooldown_manager = SuccessfulCooldownManager()
    manager.template_manager = DummyTemplateManager()
    manager.resource_status = DummyResourceStatus()
    manager.param_collector = ParamCollector(network_utils=None, config=manager.config)
    manager.image_generator = DummyImageGenerator()

    result = await manager.generate_meme(
        DummyEvent(
            "3085974225",
            "aiocqhttp:GroupMessage:20002",
            messages=[
                Comp.Reply(
                    id="123",
                    sender_id="3085974225",
                    sender_nickname="protected",
                    chain=[Comp.Image.fromBytes(b"quoted-image")],
                )
            ],
            message_str="摸头",
        )
    )

    assert result == b"generated"
