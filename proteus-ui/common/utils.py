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


def inject_button_theme(
    *,
    height: str = "44px",
    radius: str = "12px",
    font_size: str = "16px",
    min_width: str = "180px",
    padding_x: str = "16px",
    gap: str = "10px",
    bg: str = "#FFFFFF",
    fg: str = "#111827",
    border_color: str = "#D5DBE2",
    border_hover: str = "#9AA4B2",
    shadow: str = "0 1px 2px rgba(16,24,40,0.05), 0 0 0 1px rgba(0,0,0,0.00)",
    shadow_hover: str = "0 2px 6px rgba(16,24,40,0.08), 0 0 0 1px rgba(0,0,0,0.00)",
    shadow_active: str = "0 1px 2px rgba(16,24,40,0.04), inset 0 1px 2px rgba(16,24,40,0.06)",
) -> None:
    """Inject consistent button styles with CSS variables.

    Call this once near the top of a page. Override any of the keyword
    parameters to tweak sizing/spacing or colors.
    """
    css = f"""
    <style>
    :root {{
        --pp-btn-height: {height};
        --pp-btn-radius: {radius};
        --pp-btn-font-size: {font_size};
        --pp-btn-min-width: {min_width};
        --pp-btn-padding-x: {padding_x};
        --pp-btn-gap: {gap};
        --pp-btn-bg: {bg};
        --pp-btn-fg: {fg};
        --pp-btn-border: {border_color};
        --pp-btn-border-hover: {border_hover};
        --pp-btn-shadow: {shadow};
        --pp-btn-shadow-hover: {shadow_hover};
        --pp-btn-shadow-active: {shadow_active};
    }}

    /* Base Streamlit button */
    div.stButton > button {{
        white-space: nowrap;
        min-width: var(--pp-btn-min-width);
        height: var(--pp-btn-height);
        padding: 0 var(--pp-btn-padding-x);
        font-size: var(--pp-btn-font-size);
        font-weight: 600;
        border-radius: var(--pp-btn-radius);
        border: 1px solid var(--pp-btn-border);
        color: var(--pp-btn-fg);
        background: var(--pp-btn-bg);
        box-shadow: var(--pp-btn-shadow);
        transition: transform .02s ease, box-shadow .2s ease, border-color .2s ease, background-color .2s ease;
    }}

    div.stButton > button:hover {{
        border-color: var(--pp-btn-border-hover);
        box-shadow: var(--pp-btn-shadow-hover);
        transform: translateY(-1px);
    }}

    div.stButton > button:active {{
        transform: translateY(0);
        box-shadow: var(--pp-btn-shadow-active);
    }}

    /* Consistent spacing around buttons */
    div.stButton {{
        margin: 0 var(--pp-btn-gap) var(--pp-btn-gap) 0;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)