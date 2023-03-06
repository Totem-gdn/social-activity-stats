from itertools import zip_longest
from logging import LogRecord
from typing import Iterable, Optional, Tuple, TypeVar
import discord_lumberjack.message_creators


T = TypeVar("T")


def chunks(
    iterable: Iterable[T], chunk_size: int, fill_value: Optional[T] = None
) -> Iterable[Tuple[Optional[T]]]:
    """
    Given an iterable, splits it into chunks of up to the given size.

    Args:
            iterable (Iterable[T]): The iterable to split into chunks.
            chunk_size (int): The size of each chunk.
            fill_value (Optional[T]): The value to fill the remaining space (if any) in the last chunk with. If the value is None, the last chunk will be shorter than the chunk size.
    """
    args = [iter(iterable)] * chunk_size
    return zip_longest(*args, fillvalue=fill_value)


class EmbedLongMessageCreator(discord_lumberjack.message_creators.EmbedMessageCreator):
    def get_description(self, record: LogRecord) -> str:
        return f"**{super().get_title(record)}**"

    def get_title(self, record: LogRecord) -> str:
        return ""
