import streamlit as st
from pathlib import Path
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

    /* Base Streamlit button (main content only) */
    section[data-testid="stMain"] div.stButton > button {{
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

    section[data-testid="stMain"] div.stButton > button:hover {{
        border-color: var(--pp-btn-border-hover);
        box-shadow: var(--pp-btn-shadow-hover);
        transform: translateY(-1px);
    }}

    section[data-testid="stMain"] div.stButton > button:active {{
        transform: translateY(0);
        box-shadow: var(--pp-btn-shadow-active);
    }}

    /* Consistent spacing around buttons (main content only) */
    section[data-testid="stMain"] div.stButton {{
        margin: 0 var(--pp-btn-gap) var(--pp-btn-gap) 0;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# --- Sidebar Settings (reusable across pages) ---
def render_sidebar_settings() -> None:
    """Render the Proteus service controls at the bottom of the sidebar.

    Adds Restart/Stop controls that interact with PM2 using the repo's
    ecosystem file. Intended to be called once after page content renders
    so it appears after any page-defined sidebar widgets.
    """
    import subprocess
    import streamlit.components.v1 as components
    from pathlib import Path

    with st.sidebar:
        st.header("Proteus Services")

        root = Path(__file__).resolve().parents[2]
        ecosystem = root / "ecosystem.config.js"

        col1, col2 = st.columns(2, gap="small")
        with col1:
            restart_clicked = st.button("Restart", use_container_width=True, key="_sidebar_restart")
        with col2:
            stop_clicked = st.button("Stop", type="secondary", use_container_width=True, key="_sidebar_stop")

        if restart_clicked:
            try:
                components.html(
                    """
                    <script>
                    (function() {
                      try {
                        var target = window.location.origin;
                        var newTab = window.open('about:blank', '_blank');
                        if (newTab && newTab.document) {
                          var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Proteus restarting…</title></head>' +
                                     '<body style="font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; padding: 24px; line-height: 1.5;">' +
                                     '<h3>Proteus is restarting…</h3>' +
                                     '<p>This tab will load Proteus automatically when it is back online.</p>' +
                                     '<script>' +
                                     '  const target = ' + JSON.stringify(target) + ';' +
                                     '  function tryLoad() { fetch(target, { cache: "no-store" }).then(function(r){ if (r && r.ok) { location.replace(target); } }).catch(function(_){}); }' +
                                     '  tryLoad(); setInterval(tryLoad, 2000);' +
                                     '</' + 'script>' +
                                     '</body></html>';
                          try { newTab.document.open(); newTab.document.write(html); newTab.document.close(); } catch (e) {}
                        }
                      } catch (e) { /* ignore */ }
                      setTimeout(function(){
                        try {
                          window.top.open('', '_self');
                          window.top.close();
                          setTimeout(function(){ location.replace('about:blank'); }, 300);
                        } catch (e) {
                          location.replace('about:blank');
                        }
                      }, 300);
                    })();
                    </script>
                    """,
                    height=0,
                )
                subprocess.Popen(
                    f'cmd /C "ping -n 2 127.0.0.1 >NUL && pm2 restart \"{ecosystem}\""',
                    cwd=str(root),
                    shell=True,
                )
                st.success("Restart signals scheduled.")
            except Exception as e:
                st.error(f"Failed to restart: {e}")

        if stop_clicked:
            try:
                components.html(
                    """
                    <script>
                    (function(){
                      function attemptClose(){
                        try { window.top.open('', '_self'); } catch(e){}
                        try { window.top.close(); } catch(e){}
                        try { window.top.location.replace('about:blank'); } catch(e){}
                      }
                      attemptClose();
                      setTimeout(attemptClose, 250);
                      setTimeout(attemptClose, 750);
                    })();
                    </script>
                    """,
                    height=0,
                )
                subprocess.Popen(
                    f'cmd /C "ping -n 4 127.0.0.1 >NUL & pm2 stop \"{ecosystem}\""',
                    cwd=str(root),
                    shell=True,
                )
                st.success("Stop signals scheduled.")
                st.caption("If the tab did not close automatically, you can close it manually.")
            except Exception as e:
                st.error(f"Failed to stop: {e}")

        st.caption(f"ecosystem: {ecosystem}")

# --- App-wide settings helpers (shared) ---
def get_ui_settings_path() -> Path:
    p = Path(__file__).resolve().parents[1] / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p / "settings.json"


def load_ui_settings() -> dict:
    try:
        sp = get_ui_settings_path()
        if sp.exists():
            import json
            with sp.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_ui_settings(data: dict) -> None:
    try:
        sp = get_ui_settings_path()
        import json
        with sp.open("w", encoding="utf-8") as f:
            json.dump(data or {}, f, indent=2)
    except Exception:
        pass


def inject_global_theme(theme: str) -> None:
    """Inject a light/dark theme by overriding base colors via CSS.

    theme: 'light' | 'dark'
    """
    mode = (theme or "").strip().lower()
    if mode not in ("light", "dark"):
        return
    if mode == "dark":
        bg = "#0f172a"  # slate-900
        text = "#e5e7eb"  # gray-200
        surface = "#111827"
        border = "#334155"
    else:
        bg = "#f8fafc"  # slate-50
        text = "#0f172a"
        surface = "#ffffff"
        border = "#d1d5db"

    css = f"""
    <style>
    .stApp, body {{ background-color: {bg} !important; color: {text} !important; }}
    /* Cards/containers */
    div[role="group"] > div {{ background-color: {surface}; }}
    /* Inputs */
    .stTextInput > div > div > input, .stSelectbox div[data-baseweb="select"] > div {{
        color: {text} !important; border-color: {border} !important;
    }}
    /* Buttons pick up from injected button theme variables */
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)