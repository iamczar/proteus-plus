import streamlit as st
import time
from common.utils import show_toast
from services.mqtt_service import MQTTService
from typing import List


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
        # Cache for discovered modules
        if "_available_modules" not in st.session_state:
            st.session_state._available_modules = []
        if "_modules_last_update" not in st.session_state:
            st.session_state._modules_last_update = 0.0

    def get_available_modules(self) -> list:
        """
        Return a list of available/connected modules as strings.

        Subscribes to module_controller/list-of-modules (once) and caches
        the latest list in session_state. Drains any queued updates each call.
        """
        try:
            topic = "module_controller/list-of-modules"
            # Ensure subscription exists
            MQTTService().subscribe(topic)
            # Drain and apply any updates
            for _, data in MQTTService().drain(topic, max_items=100):
                if isinstance(data, dict) and data.get("command") == "module_list":
                    modules = data.get("modules") or []
                    # Normalize to strings for UI selectbox
                    str_modules: List[str] = [str(m) for m in modules if m is not None]
                    # Sort descending or as-is; here we keep insertion order but unique
                    unique = []
                    for m in str_modules:
                        if m not in unique:
                            unique.append(m)
                    st.session_state._available_modules = unique
                    st.session_state._modules_last_update = time.time()
            return st.session_state._available_modules or []
        except Exception:
            # Fallback to previous cache
            return st.session_state.get("_available_modules", [])

    def select_module(self):
        col1, col2 = st.columns([1, 1])
        with col1:
            with st.container(border=True, key="module_selection_container"):
                modules = self.get_available_modules()
                if not modules:
                    st.info("No modules detected. Waiting for module_controller/list-of-modules...")
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
                    chosen = st.selectbox(
                        label="Module Selection:",
                        options=[placeholder_label] + modules,
                        index=0,
                        key="_module_select_first",
                    )
                else:
                    chosen = st.selectbox(
                        label="Module Selection:",
                        options=modules,
                        index=(modules.index(previous_value) if previous_value in modules else 0),
                        key="_module_select_final",
                    )

                self.selected_modules = st.session_state.get("selected_module")

                if chosen != placeholder_label and chosen != previous_value:
                    st.session_state.selected_module = chosen
                    show_toast(
                        f"Selected module: **{chosen}**",
                        "success",
                        source="Module Selection",
                    )
                    st.rerun()