"""Isolated OpenAI SDK 2.47 structured-format compatibility boundary."""

from openai import __version__ as openai_version
from openai.types.responses.response_format_text_config_param import (
    ResponseFormatTextConfigParam,
)
from pydantic import BaseModel

from mathloop.providers.base import ModelProviderError

SUPPORTED_OPENAI_SDK_VERSION = "2.47.0"


def strict_text_format_for_schema(
    schema: type[BaseModel],
) -> ResponseFormatTextConfigParam:
    """Return the exact strict text format used internally by Responses.parse()."""
    if openai_version != SUPPORTED_OPENAI_SDK_VERSION:
        raise ModelProviderError(
            "OpenAI private structured-format adapter requires SDK "
            f"{SUPPORTED_OPENAI_SDK_VERSION}, found {openai_version}"
        )
    from openai.lib._parsing._responses import type_to_text_format_param

    return type_to_text_format_param(schema)
