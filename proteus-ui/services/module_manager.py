import streamlit as st
import time
from common.utils import show_toast


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class ModuleManager(metaclass=Singleton):
    def __init__(self):
        self.current_page = None
        self.selected_modules = None
        # Placeholder list; replaced at runtime by `get_available_modules()`

    def get_available_modules(self) -> list:
        """
        Return a list of available/connected modules as strings.

        NOTE: This is a placeholder implementation. Replace the body of this
        method to return the actual connected modules when the backend wiring
        is ready (e.g., query a service, read from cache, etc.).
        """
        return ["3005", "3006", "3007"]

    def select_module(self):
        col1, col2 = st.columns([1, 1])
        with col1:
            with st.container(border=True, key="module_selection_container"):
                modules = self.get_available_modules()
                if not modules:
                    st.info("No modules detected.")
                    return

                previous_value = st.session_state.get("selected_module")
                if previous_value is not None and previous_value not in modules:
                    try:
                        del st.session_state["selected_module"]
                    except Exception:
                        pass
                    previous_value = None

                placeholder_label = "— Select a module —"
                if previous_value is None:
                    # No selection yet: render with placeholder (separate key)
                    chosen = st.selectbox(
                        label="Module Selection:",
                        options=[placeholder_label] + modules,
                        index=0,
                        key="_module_select_first",
                    )
                else:
                    # Selection exists: render without placeholder (different key)
                    chosen = st.selectbox(
                        label="Module Selection:",
                        options=modules,
                        index=(modules.index(previous_value) if previous_value in modules else 0),
                        key="_module_select_final",
                    )

                # Save it in instance variable too if needed
                self.selected_modules = st.session_state.get("selected_module")

                # Update selection only when a real module is chosen, and toast on change
                if chosen != placeholder_label and chosen != previous_value:
                    st.session_state.selected_module = chosen
                    show_toast(
                        f"Selected module: **{chosen}**",
                        "success",
                        source="Module Selection",
                    )
                    # Remove placeholder by switching to final widget on next render
                    st.rerun()