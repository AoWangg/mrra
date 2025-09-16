from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import Runnable
except Exception:  # pragma: no cover
    ChatPromptTemplate = None  # type: ignore
    Runnable = object  # type: ignore

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore


def make_llm(
    provider: str,
    model: str,
    base_url: str | None,
    api_key: str | None,
    temperature: float = 0.2,
    timeout: float | None = 60.0,
    **kwargs,
) -> Any:
    """Create an OpenAI-compatible chat model via langchain-openai.

    Requires environment to have langchain-openai installed.
    """
    if ChatOpenAI is None:
        raise ImportError("langchain-openai is required to build LLM client")
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        timeout=timeout,
        **kwargs,
    )


def _default_prompt(name: str) -> ChatPromptTemplate:
    if ChatPromptTemplate is None:
        raise ImportError("langchain-core is required for prompts")
    system = (
        f"You are the {name} reasoning agent. "
        "Return one single JSON object only. No Markdown, no backticks, no prose."
    )
    human = (
        "任务: {task}\n"
        "候选 Options(每项含 id/lat/lon/score 等): {options}\n"
        "相关证据: {evidence}\n"
        "历史: {history}\n"
        "请在 Options 中的 id 里做选择，不要输出经纬度数字。\n"
        "严格返回一个 JSON 对象(仅一行，无前后缀)，键包含 selection 或 path_ids、confidence、rationale。\n"
        '示例(JSON): {{"selection":["g_17243_57923"],"confidence":0.85,"rationale":"解释你的理由"}}'
    )
    return ChatPromptTemplate.from_messages([("system", system), ("human", human)])


def build_subagent(name: str, llm: Any, prompt: str | None, tools: List[Any]) -> Any:
    logger = logging.getLogger("mrra.subagents")
    if not prompt:
        template = _default_prompt(name)
    else:
        system = (
            f"You are the {name} reasoning agent. "
            "Return one single JSON object only. No Markdown, no backticks, no prose."
        )
        human = (
            prompt + "\n\n" + "任务: {task}\n"
            "候选 Options(每项含 id/lat/lon/score 等): {options}\n"
            "相关证据: {evidence}\n"
            "历史: {history}\n"
            "请在 Options 中的 id 里做选择，不要输出经纬度数字。\n"
            "严格返回一个 JSON 对象(仅一行，无前后缀)，键包含 selection 或 path_ids、confidence、rationale。\n"
            '示例(JSON): {{"selection":["g_17243_57923"],"confidence":0.85,"rationale":"解释你的理由"}}'
        )
        template = ChatPromptTemplate.from_messages(
            [("system", system), ("human", human)]
        )
        template = template.partial(
            schema='{"proposal":{"type":"point","value":[lat,lon]},"confidence":0.5,"rationale":"中文解释理由"}',
            example='{"proposal":{"type":"point","value":[31.2304,121.4737]},"confidence":0.62,"rationale":"根据证据1/2..."}',
        )

    # Bind tools if provided
    chain = template | llm
    if hasattr(llm, "bind_tools") and tools:
        chain = template | llm.bind_tools(tools)

    # Wrap to ensure JSON parsing and consistent dict output
    def _runner(inputs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            ev_len = (
                len(inputs.get("evidence", []))
                if isinstance(inputs.get("evidence"), list)
                else 0
            )
        except Exception:
            ev_len = 0
        logger.debug(
            f"subagent[{name}] invoking; task={inputs.get('task')} evidence_len={ev_len}"
        )

        msg = chain.invoke(inputs)
        content = getattr(msg, "content", msg)
        if not isinstance(content, str):
            # Some models return BaseMessage
            content = getattr(content, "content", str(content))
        logger.debug(f"subagent[{name}] raw content: {content[:500]!r}")
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict) or (
                "selection" not in parsed and "path_ids" not in parsed
            ):
                logger.warning(
                    f"subagent[{name}] non-standard JSON schema keys={list(parsed) if isinstance(parsed, dict) else type(parsed)}"
                )
                return {
                    "_raw": parsed,
                    "selection": [],
                    "confidence": 0.0,
                    "rationale": "non-standard schema",
                }
            logger.debug(f"subagent[{name}] parsed keys: {list(parsed.keys())}")
            return parsed
        except Exception:
            # attempt to extract JSON substring
            import re

            m = re.search(r"\{[\s\S]*\}", content)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                    if not isinstance(parsed, dict) or (
                        "selection" not in parsed and "path_ids" not in parsed
                    ):
                        logger.warning(
                            f"subagent[{name}] JSON substring non-standard schema"
                        )
                        return {
                            "_raw": parsed,
                            "selection": [],
                            "confidence": 0.0,
                            "rationale": "non-standard schema",
                        }
                    logger.debug(
                        f"subagent[{name}] parsed-from-substring keys: {list(parsed.keys())}"
                    )
                    return parsed
                except Exception:
                    pass
        # 返回诊断结构，不做兜底推断
        logger.error(f"subagent[{name}] failed to parse JSON output")
        return {
            "_raw_text": content[:2000],
            "selection": [],
            "confidence": 0.0,
            "rationale": "parse_error",
        }

    return _runner
