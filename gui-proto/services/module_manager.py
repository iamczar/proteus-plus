import streamlit as st
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
        self.selected_modules = "All"
        # TODO: remove All from options

    def select_module(self):
        col1, col2 = st.columns([1, 1])
        with col1:
            with st.container(border=True, key="module_selection_container"):
                if "selected_module" not in st.session_state:
                    st.session_state.selected_module = self.selected_modules

                # TODO: remove toast trigger when navigating to another module-selectable page
                # TODO: can do this with a previous page state cache

                # Multiselect that is *bound* to session state
                st.segmented_control(
                    label="Module Selection",
                    options=["All", "9001", "2501", "3006"],
                    key="selected_module",  # this binds the value, no need for `default`
                    selection_mode="single"
                )

                # Save it in instance variable too if needed
                self.selected_modules = st.session_state.selected_module
                show_toast(f"Selected module: **{self.selected_modules}**", "info")
