"""Streamlit chat interface for the conversational agent."""

import json
import uuid

import httpx
import streamlit as st

BACKEND_URL = "http://localhost:8000/api"


def init_session():
    """Initialize session state."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []


def reset_conversation():
    """Reset conversation and create new session."""
    old_session_id = st.session_state.session_id
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []

    try:
        httpx.delete(f"{BACKEND_URL}/session/{old_session_id}", timeout=5.0)
    except Exception:
        pass


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
        st.header("Session Info")
        st.caption(f"Session ID: {st.session_state.session_id[:8]}...")

        if st.button("🔄 New Conversation", use_container_width=True):
            reset_conversation()
            st.rerun()

        st.divider()

        st.markdown("""
        ### What I can help with:
        - **Company Information**: Ask about the company's financials, business, or strategy
        - **Order Status**: Check your order shipment status (requires verification)

        ### For order status:
        I'll need to verify your identity with:
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
                for chunk in asyncio.run(stream_chat(prompt)):
                    if chunk:
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")

                message_placeholder.markdown(full_response)
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response}
                )

            except Exception as e:
                error_msg = f"Failed to connect to backend: {str(e)}"
                st.error(error_msg)
                st.info("Make sure the backend is running at http://localhost:8000")


if __name__ == "__main__":
    main()
