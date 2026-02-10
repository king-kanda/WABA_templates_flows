"""Groq-powered AI agent with tool-calling for car rental business."""

import json
import logging
import os
from datetime import datetime
from groq import AsyncGroq
from app.config import get_settings
from app.services.conversation import save_message, load_history
from app.tools.definitions import TOOLS
from app.tools.handlers import dispatch_tool

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5

# Load system prompt
_prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts",
                            "system_prompt.txt")
with open(_prompt_path, "r") as f:
    SYSTEM_PROMPT = f.read()


async def process_message(wa_id: str,
                          user_message: str,
                          media_context: str | None = None) -> str:
    """
    Process an incoming message through the Groq agent.
    Returns the agent's text response to send back to the user.
    """
    settings = get_settings()
    client = AsyncGroq(api_key=settings.groq_api_key)

    # Build the user message with any media context
    full_message = user_message
    if media_context:
        full_message = f"[The customer just sent an image/document. {media_context}]\n\n{user_message}" if user_message else f"[The customer just sent an image/document. {media_context}]"

    # Save user message
    await save_message(wa_id, "user", full_message)

    # Load conversation history
    history = await load_history(wa_id)

    # Build messages for Groq
    today = datetime.now().strftime("%Y-%m-%d")
    system = f"{SYSTEM_PROMPT}\n\nToday's date: {today}\nCustomer's WhatsApp number: {wa_id}"

    messages = [{"role": "system", "content": system}] + history

    # Agent loop
    for iteration in range(MAX_ITERATIONS):
        try:
            response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=1024,
                temperature=0.7,
            )
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return "I'm having trouble processing your request right now. Please try again in a moment."

        choice = response.choices[0]
        assistant_msg = choice.message

        # If there are tool calls, execute them
        if assistant_msg.tool_calls:
            # Save assistant message with tool calls
            tool_calls_data = [{
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            } for tc in assistant_msg.tool_calls]
            await save_message(
                wa_id,
                "assistant",
                content=assistant_msg.content,
                tool_calls=tool_calls_data,
            )

            # Add assistant message to context
            msg_dict = {
                "role": "assistant",
                "content": assistant_msg.content,
                "tool_calls": tool_calls_data
            }
            messages.append(msg_dict)

            # Execute each tool call
            for tool_call in assistant_msg.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments

                logger.info(
                    f"Executing tool: {tool_name} with args: {tool_args}")
                result = await dispatch_tool(tool_name, tool_args)

                # Save tool result
                await save_message(wa_id,
                                   "tool",
                                   content=result,
                                   tool_call_id=tool_call.id)

                # Add to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            # Continue loop to get final text response
            continue

        # No tool calls — return the text response
        reply = assistant_msg.content or "I'm not sure how to respond to that. Could you rephrase?"
        await save_message(wa_id, "assistant", reply)
        return reply

    # If we exhausted iterations
    fallback = "I've been working on your request but need a moment. Could you try sending your message again?"
    await save_message(wa_id, "assistant", fallback)
    return fallback
