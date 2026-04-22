"""Streamlit chat interface for the conversational agent."""

import json
import os
import uuid

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080/api")


def init_session():
    """Initialize session state."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversations" not in st.session_state:
        st.session_state.conversations = {
            st.session_state.session_id: {
                "title": "New Conversation",
                "messages": []
            }
        }


def reset_conversation():
    """Reset conversation and create new session."""
    old_session_id = st.session_state.session_id

    # Save current conversation
    if st.session_state.messages:
        first_msg = st.session_state.messages[0]["content"][:50]
        st.session_state.conversations[old_session_id] = {
            "title": first_msg,
            "messages": st.session_state.messages.copy()
        }

    # Create new session
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.conversations[st.session_state.session_id] = {
        "title": "New Conversation",
        "messages": []
    }

    try:
        httpx.delete(f"{BACKEND_URL}/session/{old_session_id}", timeout=5.0)
    except Exception:
        pass


def load_conversation(session_id: str):
    """Load a previous conversation."""
    if session_id in st.session_state.conversations:
        st.session_state.session_id = session_id
        st.session_state.messages = st.session_state.conversations[session_id]["messages"].copy()
        st.rerun()


def parse_sse_event(line: str) -> dict | None:
    """Parse a single SSE event line."""
    if line.startswith("data: "):
        try:
            return json.loads(line[6:])
        except json.JSONDecodeError:
            return None
    return None


async def stream_chat(message: str):
    """Stream chat response from backend."""
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{BACKEND_URL}/chat",
            json={"session_id": st.session_state.session_id, "message": message},
            timeout=60.0,
        ) as response:
            current_tool = None
            tool_placeholder = None

            async for line in response.aiter_lines():
                if not line:
                    continue

                event = parse_sse_event(line)
                if not event:
                    continue

                event_type = event.get("type")

                if event_type == "token":
                    if tool_placeholder:
                        tool_placeholder.empty()
                        tool_placeholder = None
                    yield event.get("data", "")

                elif event_type == "tool_start":
                    tool_name = event.get("data", {}).get("tool", "unknown")
                    current_tool = tool_name
                    tool_placeholder = st.empty()
                    if "order" in tool_name.lower():
                        tool_placeholder.info("🔍 Checking order status...")
                    elif "knowledge" in tool_name.lower():
                        tool_placeholder.info("📚 Searching knowledge base...")
                    else:
                        tool_placeholder.info(f"🔧 Using tool: {tool_name}")

                elif event_type == "tool_end":
                    if tool_placeholder:
                        tool_placeholder.empty()
                        tool_placeholder = None

                elif event_type == "error":
                    error_msg = event.get("data", "Unknown error")
                    st.error(f"Error: {error_msg}")

                elif event_type == "done":
                    if tool_placeholder:
                        tool_placeholder.empty()
                    break


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="E-Commerce Assistant",
        page_icon="🤖",
        layout="centered",
    )

    st.title("🤖 E-Commerce Customer Assistant")

    init_session()

    with st.sidebar:
        if st.button("➕ New Conversation", use_container_width=True):
            reset_conversation()
            st.rerun()

        st.divider()

        st.subheader("Conversations")

        # Show conversation list
        for sess_id, conv in sorted(
            st.session_state.conversations.items(),
            key=lambda x: x[0],
            reverse=True
        ):
            is_current = sess_id == st.session_state.session_id
            label = conv["title"]

            if is_current:
                st.markdown(f"**▶ {label}**")
            else:
                if st.button(
                    label,
                    key=f"load_{sess_id}",
                    use_container_width=True,
                    type="secondary"
                ):
                    load_conversation(sess_id)

        st.divider()

        st.markdown("""
        ### What I can help with:
        - **Company Information**: Ask about financials, business, strategy
        - **Order Status**: Check shipment (requires verification)

        ### For order status:
        - Full name
        - Last 4 digits of SSN
        - Date of birth
        """)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("How can I help you today?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""

            try:
                import asyncio

                async def run_stream():
                    chunks = []
                    async for chunk in stream_chat(prompt):
                        if chunk:
                            chunks.append(chunk)
                            full = "".join(chunks)
                            message_placeholder.markdown(full + "▌")
                    return "".join(chunks)

                full_response = asyncio.run(run_stream())
                message_placeholder.markdown(full_response)
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response}
                )

                # Update conversation title from first message
                if len(st.session_state.messages) == 2:
                    first_user_msg = st.session_state.messages[0]["content"][:50]
                    st.session_state.conversations[st.session_state.session_id]["title"] = first_user_msg

                # Save messages to conversation
                st.session_state.conversations[st.session_state.session_id]["messages"] = st.session_state.messages.copy()

            except Exception as e:
                error_msg = f"Failed to connect to backend: {str(e)}"
                st.error(error_msg)
                st.info("Make sure the backend is running at http://localhost:8000")


if __name__ == "__main__":
    main()
