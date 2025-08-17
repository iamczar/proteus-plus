import streamlit as st
import random
import time


def show_toast(message: str, status: str = "success", duration: float = 5.0, source: str | None = None) -> None:
    """
    Unified toast helper: queues a persistent, in-page message.

    - Does NOT use Streamlit's built-in st.toast (which fades quickly and overlaps UI)
    - Pages should render messages by calling `render_toast_area()` at an appropriate location
    """
    if "_toasts" not in st.session_state:
        st.session_state._toasts = []
    st.session_state._toasts.append({
        "message": message,
        "status": status,
        "expires": time.time() + max(duration, 0.1),
        "source": source,
    })


def render_toast_area(max_messages: int = 3, container=None) -> None:
    """Render the last few queued toasts. If a `container` (placeholder.container())
    is provided, the content will replace previous content to avoid duplicates.
    Call this in a stable UI position (e.g., between controls and charts).
    """
    if "_toasts" not in st.session_state:
        st.session_state._toasts = []

    # Filter out expired messages
    now = time.time()
    valid_toasts = [t for t in st.session_state._toasts if t.get("expires", 0) > now]
    st.session_state._toasts = valid_toasts

    # Always render into a known container to clear previous content
    target = container if container is not None else st.container()
    if not valid_toasts:
        with target:
            # Clear when no toasts
            st.empty()
        return
    # Show newest first: take the last N, then reverse so the most recent is on top
    to_show = list(reversed(valid_toasts[-max_messages:]))
    with target:
        for t in to_show:
            status = t.get("status", "info")
            src = t.get("source")
            base = t.get("message", "")
            msg = f"[{src}] {base}" if src else base
            if status == "success":
                st.success(msg)
            elif status == "error":
                st.error(msg)
            elif status == "warning":
                st.warning(msg)
            else:
                st.info(msg)


def random_color():
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))


def fixed_footer():
    st.markdown("""
        <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: #f1f1f1;
            color: black;
            text-align: center;
            padding: 10px;
            border-top: 1px solid #ccc;
            z-index: 9999;
        }
        </style>
        <div class="footer">
            © 2025 My Streamlit App | <a href='https://example.com' target='_blank'>Help</a>
        </div>
    """, unsafe_allow_html=True)
