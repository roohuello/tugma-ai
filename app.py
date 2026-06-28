import logging

import chainlit as cl
from langchain_core.messages import AIMessageChunk, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from src.agents.main_agent import build_agent
from src.core.guardrails import check_input
from src.core.redis import get_checkpointer, get_store
from src.observability.langfuse import get_langfuse_handler

logger = logging.getLogger(__name__)

# ponytail: lazy singleton init — one setup per process lifetime
_saver = None
_store = None


async def _setup_state():
    global _saver, _store
    if _saver is not None:
        return
    try:
        _saver = get_checkpointer()
        await _saver.asetup()
        _store = get_store()
        await _store.setup()
    except Exception as e:
        logger.warning("Redis unavailable (%s) — using in-memory state. Session data won't persist.", e)
        _saver = MemorySaver()
        _store = InMemoryStore()


@cl.on_chat_start
async def on_chat_start():
    await _setup_state()

    agent = build_agent(checkpointer=_saver, store=_store)
    cl.user_session.set("agent", agent)

    await cl.Message(
        content="Welcome sa Tugma! Ano'ng career ang nasa isip mo? "
    ).send()


@cl.on_message
async def on_message(msg: cl.Message):
    passed, reason = check_input(msg.content)
    if not passed:
        await cl.Message(
            content="Sorry, may nakita akong sensitibong impormasyon o hindi angkop na "
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

    input_msg = {"messages": [HumanMessage(content=msg.content)]}

    async with cl.Step(name="Getting to know you...", type="run") as step:
        step.input = msg.content
        final_msg = cl.Message(content="")

        async for mode, *data in agent.astream(
            input_msg,
            stream_mode=["messages", "custom"],
            config=config,
        ):
            if mode == "messages":
                msg_chunk, _ = data[0]
                if isinstance(msg_chunk, AIMessageChunk) and msg_chunk.content:
                    await final_msg.stream_token(msg_chunk.content)
            elif mode == "custom":
                chunk = data[0]
                chunk_type = chunk.get("type")

                if chunk_type == "stage":
                    if final_msg.content:
                        await final_msg.send()
                        final_msg = cl.Message(content="")
                    step.name = chunk["name"]
                    await step.update()

        if final_msg.content:
            await final_msg.send()
