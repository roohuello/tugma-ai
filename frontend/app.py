import logging

import chainlit as cl
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from src.agents.main_agent import build_agent
from src.core.guardrails import check_input
from src.core.redis import get_checkpointer, get_store
from src.observability.langfuse import get_langfuse_handler, profile_completeness

logger = logging.getLogger(__name__)

# ponytail: lazy singleton init — one setup per process lifetime
_saver = None
_store = None
_redis_unavailable = False


async def _setup_state():
    global _saver, _store, _redis_unavailable
    if _saver is not None:
        return
    try:
        _saver = get_checkpointer()
        await _saver.asetup()
        _store = get_store()
        await _store.asetup()
    except Exception as e:
        logger.warning("Redis unavailable (%s) — using in-memory state. Session data won't persist.", e)
        _saver = MemorySaver()
        _store = InMemoryStore()
        _redis_unavailable = True


@cl.on_chat_start
async def on_chat_start():
    await _setup_state()

    agent = build_agent(checkpointer=_saver, store=_store)
    cl.user_session.set("agent", agent)

    await cl.Message(
        content="Maligayang pagdating sa Tugma! Ano'ng career ang nasa isip mo? "
        "Pwedeng Tagalog, Taglish, o English."
    ).send()


@cl.on_message
async def on_message(msg: cl.Message):
    passed, reason = check_input(msg.content)
    if not passed:
        await cl.Message(
            content="Paumanhin, may nakita akong sensitibong impormasyon o hindi angkop na "
            "pananalita sa iyong mensahe. Subukan mong muling ipahayag ito."
        ).send()
        return

    agent = cl.user_session.get("agent")
    langfuse_handler = get_langfuse_handler()
    cb = cl.LangchainCallbackHandler()

    callbacks = [cb]
    if langfuse_handler:
        callbacks.append(langfuse_handler)

    config = {
        "callbacks": callbacks,
        "configurable": {"thread_id": cl.context.session.id},
    }

    interrupted = cl.user_session.get("interrupted")
    if interrupted:
        cl.user_session.set("interrupted", False)
        input_msg = Command(resume={"decisions": [{"type": "approve"}]})
    else:
        input_msg = {"messages": [HumanMessage(content=msg.content)]}

    async with cl.Step(name="Getting to know you...", type="run") as step:
        step.input = msg.content
        final_msg = cl.Message(content="")

        async for mode, chunk in agent.astream(
            input_msg,
            stream_mode=["custom"],
            version="v2",
            config=config,
        ):
            if mode == "custom":
                chunk_type = chunk.get("type")

                if chunk_type == "stage":
                    step.name = chunk["name"]
                elif chunk_type == "recommendations":
                    for subject in chunk["data"]["recommendations"]:
                        await cl.Message(
                            content="",
                            elements=[
                                cl.CustomElement(
                                    name="ElectiveCard",
                                    props=subject,
                                    display="inline",
                                )
                            ],
                        ).send()
                    if langfuse_handler and hasattr(langfuse_handler, "current_span"):
                        span = langfuse_handler.current_span
                        if span:
                            from src.models.profile import StudentProfile
                            try:
                                profile = StudentProfile(**chunk["data"]["profile"])
                                span.score(
                                    name="profile_completeness",
                                    value=profile_completeness(profile),
                                    data_type="NUMERIC",
                                )
                            except Exception:
                                pass
                elif chunk_type == "token":
                    await final_msg.stream_token(chunk["content"])

        step.output = "Done"
        await final_msg.send()

    state = agent.get_state(config)
    if state.next:
        cl.user_session.set("interrupted", True)
