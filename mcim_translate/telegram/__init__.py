from typing import List, Optional, Union
from telegram.helpers import escape_markdown
import httpx
import tenacity

from mcim_translate.config import Config
from mcim_translate.logger import log
from mcim_translate.constants import Platform

telegram_config = Config.load().telegram

TELEGRAM_MAX_CHARS = 4096  # Telegram 文本消息最大长度

def _make_spoiler_block_with_budget(lines: List[str], budget: int, prefix: str = "> ") -> str:
    """
    将 lines 按行拼接到 spoiler 中，确保拼接后的内容长度不超过 budget。
    注意：budget 应该已扣除 spoiler 包裹符号 '||' 的长度。
    """
    assembled_lines: List[str] = []
    used = 0
    for line in lines:
        # 逐行转义并加入前缀
        escaped_line = f"{prefix}{escape_markdown(line, version=2)}"
        # 如果不是第一行，需要额外的换行符
        increment = len(escaped_line) + (1 if assembled_lines else 0)
        if used + increment > budget:
            break
        assembled_lines.append(escaped_line)
        used += increment
    return f"**{'\n'.join(assembled_lines)}||"


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


def send_result(platform: Platform, project_ids: List[Union[int, str]]) -> int:
    if platform == Platform.CURSEFORGE:
        header_raw = f"已翻译 {len(project_ids)} 个 Curseforge 模组，以下为模组 ID:\n"
        footer_raw = "\n#Curseforge_Translate"
    elif platform == Platform.MODRINTH:
        header_raw = f"已翻译 {len(project_ids)} 个 Modrinth 项目，以下为项目 ID:\n"
        footer_raw = "\n#Modrinth_Translate"
    else:
        raise ValueError(f"Unknown platform: {platform}")

    # 先转义头尾
    header = escape_markdown(header_raw, version=2)
    footer = escape_markdown(footer_raw, version=2)

    # 预留 spoiler 包裹符号 '**' + '||' 的 4 个字符
    budget_for_lines = TELEGRAM_MAX_CHARS - len(header) - len(footer) - 4

    id_lines = [str(pid) for pid in project_ids]
    spoiler_block = _make_spoiler_block_with_budget(id_lines, budget_for_lines, prefix="> ")

    message = f"{header}{spoiler_block}{footer}"

    return send_message_sync(
        message,
        telegram_config.chat_id,
        parse_mode="MarkdownV2"
    )