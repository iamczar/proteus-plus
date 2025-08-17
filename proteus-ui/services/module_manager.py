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

                if "selected_module" not in st.session_state:
                    # Default to the first available module
                    st.session_state.selected_module = modules[0]

                # TODO: remove toast trigger when navigating to another module-selectable page
                # TODO: can do this with a previous page state cache

                # Dropdown (single-select) bound to session state
                new_value = st.selectbox(
                    label="Module Selection:",
                    options=modules,
                    key="selected_module",
                )

                # Save it in instance variable too if needed
                self.selected_modules = st.session_state.selected_module
                # Add to persistent toast area with source label for clarity
                show_toast(f"Selected module: **{self.selected_modules}**", "info", source="Module Selection")