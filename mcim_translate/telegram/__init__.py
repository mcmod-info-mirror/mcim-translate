from typing import List, Optional, Union
from telegram.helpers import escape_markdown as _escape_markdown
import httpx
import tenacity

from mcim_translate.config import Config
from mcim_translate.logger import log
from mcim_translate.constants import Platform

telegram_config = Config.load().telegram


def escape_markdown(text: str) -> str:
    return _escape_markdown(text=text, version=2)


@tenacity.retry(
    # retry=tenacity.retry_if_exception_type(TelegramError, NetworkError), # 无条件重试
    wait=tenacity.wait_fixed(1),
    stop=tenacity.stop_after_attempt(10),
)
def send_message_sync(
    text: str,
    chat_id: str,
    parse_mode: Optional[str] = None,
) -> int:
    data = {
        "chat_id": chat_id,
        "text": text,
        # TODO: 支持 Markdown
    }
    if parse_mode:
        data["parse_mode"] = parse_mode
    result = httpx.post(
        f"{telegram_config.bot_api}{telegram_config.bot_token}/sendMessage",
        json=data,
    ).json()
    if result["ok"]:
        log.info(
            f"Message '{text}' sent to telegram, message_id: {result['result']['message_id']}"
        )
        return result["result"]["message_id"]
    else:
        raise Exception(
            f"Telegram API error: {result}, original message: {repr(text)}, parse_mode: {parse_mode}"
        )

def make_blockquote(lines: List[str], prefix: str = "> ") -> str:
    return (
        "**" + "\n".join([f"{prefix}{escape_markdown(line)}" for line in lines]) + "||"
    )


def make_project_detail_blockquote(project_ids: List[Union[int, str]]) -> str:
    """
    制作模组信息的折叠代码块
    """
    mod_messages = []
    message_length = 0
    for project_id in project_ids:
        if message_length >= 3600:  # 不算代码块标识符的长度
            break
        text = f"{project_id}"
        mod_messages.append(text)
        message_length += len(text)
    message = make_blockquote(mod_messages)
    return message

def send_result(platform: Platform, project_ids: List[Union[int, str]]) -> int:
    if platform == Platform.CURSEFORGE:
        message = escape_markdown(f'已翻译 {len(project_ids)} 个 Curseforge 模组，以下为模组 ID:\n')
        message += make_project_detail_blockquote(project_ids)
        message += escape_markdown("\n#Curseforge_Translate")
    elif platform == Platform.MODRINTH:
        message = escape_markdown(f'已翻译 {len(project_ids)} 个 Modrinth 项目，以下为项目 ID:\n')
        message += make_project_detail_blockquote(project_ids)
        message += escape_markdown("\n#Modrinth_Translate")
    else:
        raise ValueError(f"Unknown platform: {platform}")
    return send_message_sync(
        message,
        telegram_config.chat_id
    )