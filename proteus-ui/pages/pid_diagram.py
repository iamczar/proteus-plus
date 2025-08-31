import os
import streamlit as st


PRIMARY_IMAGE_PATH = "assets/PI&D.png"


def _render_image() -> None:
    st.title("PI&D")
    if os.path.exists(PRIMARY_IMAGE_PATH):
        st.image(PRIMARY_IMAGE_PATH, caption="PI&D overview", use_container_width=True)
    else:
        st.warning("PI&D image not found.")
        st.info(
            "Place the provided image at 'proteus-ui/{}' and refresh the page.".format(
                PRIMARY_IMAGE_PATH
            )
        )


def main() -> None:
    st.session_state["_current_page_key"] = "proteus_ui_pid_diagram"
    _render_image()


if __name__ == "__main__":
    main()


