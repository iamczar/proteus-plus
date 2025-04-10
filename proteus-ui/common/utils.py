import streamlit as st
import random


def show_toast(message, status="success"):
    color_map = {
        "success": ("#45BE89", "#00775a"),
        "error": ("#D3616A", "#B71C1C"),
        "warning": ("#FFB839", "#CC8400"),
        "info": ("#62B9F3", "#1565C0"),
    }

    bg, border = color_map.get(status, ("#444", "#222"))

    st.toast(message)

    # Inject CSS to style the toast
    st.markdown(f"""
    <style>
    [data-testid="stToast"] {{
        background-color: {bg} !important;
        color: white !important;
        font-weight: bold;
        border: 2px solid {border};
    }}
    </style>
    """, unsafe_allow_html=True)


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
