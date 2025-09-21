import time
import os
import json

import streamlit as st
import pandas as pd
import altair as alt

from common.utils import inject_button_theme
from services.module_manager import ModuleManager
from services.mqtt_service import MQTTService
from datetime import datetime


st.set_page_config(page_title="PID Charts", layout="wide")
st.title("PID Charts")

inject_button_theme(height="32px", min_width="110px", font_size="14px", padding_x="10px")

MAX_POINTS = 1800

if "pt_selected_module" not in st.session_state:
    st.session_state.pt_selected_module = None

 


def get_mqtt() -> MQTTService:
    if "_pt_mqtt" not in st.session_state:
        st.session_state._pt_mqtt = MQTTService()
    return st.session_state._pt_mqtt


def _pt_append_log(message: str) -> None:
    try:
        payload = {
            "message_source": "proteus-ui",
            "timestamp": datetime.now().isoformat(),
            "module": st.session_state.get("pt_selected_module"),
            "message": message,
        }
        get_mqtt().publish("debug/pid", payload)
    except Exception:
        pass


ModuleManager().select_module()
global_selected = st.session_state.get("selected_module")
prev_local = st.session_state.get("pt_selected_module")
if global_selected != prev_local:
    st.session_state.pt_selected_module = global_selected
    _pt_append_log(f">> Selected module: {global_selected}")


 


def _append_live_point(payload: dict) -> None:
    try:
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            return
        ts = payload.get("timestamp") or payload.get("time") or payload.get("ts")
        try:
            t_epoch = int(time.time()) if ts is None else int(pd.to_datetime(ts, utc=True).timestamp())
        except Exception:
            t_epoch = int(time.time())
        buf = st.session_state.pt_data
        buf["t"].append(t_epoch)
        buf["ox_desired"].append(float(data.get("oxygen_setpoint", 0.0)))
        buf["ox_meas1"].append(float(data.get("oxygen_measured_1", 0.0)))
        buf["ox_meas2"].append(float(data.get("oxygen_measured_2", 0.0)))
        buf["ox_meas3"].append(float(data.get("oxygen_measured_3", 0.0)))
        buf["flow_desired"].append(float(data.get("circ_flow_speed_desired", 0.0)))
        buf["flow_actual"].append(float(data.get("flow_measured", 0.0)))
        buf["press_pump_desired"].append(float(data.get("pressure_flow_speed_desired", 0.0)))
        buf["press_pump_actual"].append(float(data.get("pressure_pump_speed", 0.0)))
        buf["pressure_desired"].append(float(data.get("pressure_setpoint", 0.0)))
        buf["pressure_actual"].append(float(data.get("pressure_measured", 0.0)))
        N = MAX_POINTS
        for k in list(buf.keys()):
            if len(buf[k]) > N:
                buf[k] = buf[k][-N:]
    except Exception:
        pass


def _ensure_buffers():
    if "pt_data" not in st.session_state:
        st.session_state.pt_data = {
            "t": [],
            "ox_desired": [],
            "ox_meas1": [],
            "ox_meas2": [],
            "ox_meas3": [],
            "flow_desired": [],
            "flow_actual": [],
            "press_pump_desired": [],
            "press_pump_actual": [],
            "pressure_desired": [],
            "pressure_actual": [],
        }


_ensure_buffers()


def _render_charts():
    st.subheader("Oxygen (desired vs measured x3)")
    df0 = pd.DataFrame({"x": [], "y": [], "series": []})
    c0 = st.altair_chart(
        alt.Chart(df0)
        .mark_line()
        .encode(
            x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
            y=alt.Y("y:Q", title=None),
            color=alt.Color("series:N", legend=alt.Legend(orient="top")),
        ),
        use_container_width=True,
    )

    st.subheader("Flow (desired speed vs actual flow)")
    df1 = pd.DataFrame({"x": [], "y": [], "series": []})
    c1 = st.altair_chart(
        alt.Chart(df1)
        .mark_line()
        .encode(
            x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
            y=alt.Y("y:Q", title=None),
            color=alt.Color("series:N", legend=alt.Legend(orient="top")),
        ),
        use_container_width=True,
    )

    st.subheader("Pressure Pump Speed (desired vs actual)")
    df2 = pd.DataFrame({"x": [], "y": [], "series": []})
    c2 = st.altair_chart(
        alt.Chart(df2)
        .mark_line()
        .encode(
            x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
            y=alt.Y("y:Q", title=None),
            color=alt.Color("series:N", legend=alt.Legend(orient="top")),
        ),
        use_container_width=True,
    )

    st.subheader("Pressure (desired vs actual)")
    df3 = pd.DataFrame({"x": [], "y": [], "series": []})
    c3 = st.altair_chart(
        alt.Chart(df3)
        .mark_line()
        .encode(
            x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
            y=alt.Y("y:Q", title=None),
            color=alt.Color("series:N", legend=alt.Legend(orient="top")),
        ),
        use_container_width=True,
    )
    st.session_state._pidc_charts = {"oxygen": c0, "flow": c1, "pressure_pump": c2, "pressure": c3}
    # Reset painted index so we repopulate after (re)creating charts
    st.session_state._pidc_painted = 0
    # Paint existing buffer immediately so charts are visible after navigation
    data = st.session_state.get("pt_data") or {}
    t = data.get("t") or []
    if t:
        rows_oxygen = {"x": [], "y": [], "series": []}
        rows_flow = {"x": [], "y": [], "series": []}
        rows_pressure_pump = {"x": [], "y": [], "series": []}
        rows_pressure = {"x": [], "y": [], "series": []}
        for i in range(len(t)):
            x_ts = pd.to_datetime(int(t[i]), unit="s")
            rows_oxygen["x"].extend([x_ts, x_ts, x_ts, x_ts])
            rows_oxygen["y"].extend([
                float(data.get("ox_desired", [0.0])[i] if len(data.get("ox_desired", [])) > i else 0.0),
                float(data.get("ox_meas1", [0.0])[i] if len(data.get("ox_meas1", [])) > i else 0.0),
                float(data.get("ox_meas2", [0.0])[i] if len(data.get("ox_meas2", [])) > i else 0.0),
                float(data.get("ox_meas3", [0.0])[i] if len(data.get("ox_meas3", [])) > i else 0.0),
            ])
            rows_oxygen["series"].extend(["Desired", "Measured 1", "Measured 2", "Measured 3"])
            rows_flow["x"].extend([x_ts, x_ts])
            rows_flow["y"].extend([
                float(data.get("flow_desired", [0.0])[i] if len(data.get("flow_desired", [])) > i else 0.0),
                float(data.get("flow_actual", [0.0])[i] if len(data.get("flow_actual", [])) > i else 0.0),
            ])
            rows_flow["series"].extend(["Desired", "Actual"])
            rows_pressure_pump["x"].extend([x_ts, x_ts])
            rows_pressure_pump["y"].extend([
                float(data.get("press_pump_desired", [0.0])[i] if len(data.get("press_pump_desired", [])) > i else 0.0),
                float(data.get("press_pump_actual", [0.0])[i] if len(data.get("press_pump_actual", [])) > i else 0.0),
            ])
            rows_pressure_pump["series"].extend(["Desired", "Actual"])
            rows_pressure["x"].extend([x_ts, x_ts])
            rows_pressure["y"].extend([
                float(data.get("pressure_desired", [0.0])[i] if len(data.get("pressure_desired", [])) > i else 0.0),
                float(data.get("pressure_actual", [0.0])[i] if len(data.get("pressure_actual", [])) > i else 0.0),
            ])
            rows_pressure["series"].extend(["Desired", "Actual"])
        if st.session_state._pidc_charts.get("oxygen"):
            st.session_state._pidc_charts["oxygen"].add_rows(pd.DataFrame(rows_oxygen))
        if st.session_state._pidc_charts.get("flow"):
            st.session_state._pidc_charts["flow"].add_rows(pd.DataFrame(rows_flow))
        if st.session_state._pidc_charts.get("pressure_pump"):
            st.session_state._pidc_charts["pressure_pump"].add_rows(pd.DataFrame(rows_pressure_pump))
        if st.session_state._pidc_charts.get("pressure"):
            st.session_state._pidc_charts["pressure"].add_rows(pd.DataFrame(rows_pressure))
        st.session_state._pidc_painted = len(t)


_render_charts()


@st.fragment(run_every=0.5)
def _collector():
    mod = st.session_state.get("pt_selected_module")
    if not mod:
        return
    try:
        topic = f"live-sensor-data/{mod}"
        if st.session_state.get("_pidc_topic") != topic:
            try:
                get_mqtt().subscribe(topic)
                st.session_state._pidc_topic = topic
            except Exception:
                pass
        updates = get_mqtt().drain(topic, max_items=500)
        for _, payload in updates:
            try:
                if not isinstance(payload, dict):
                    continue
                if payload.get("message_source") != "data_logger":
                    continue
                _append_live_point(payload)
            except Exception:
                continue
    except Exception:
        pass


@st.fragment(run_every=0.5)
def _render_tick():
    data = st.session_state.get("pt_data") or {}
    t = data.get("t") or []
    charts = st.session_state.get("_pidc_charts") or {}
    if not t or not charts:
        return
    def build_rows(x_idx: int):
        x_ts = pd.to_datetime(int(t[x_idx]), unit="s")
        return x_ts
    start = int(st.session_state.get("_pidc_painted", 0))
    end = len(t)
    if end <= start:
        return
    rows_oxygen = {"x": [], "y": [], "series": []}
    rows_flow = {"x": [], "y": [], "series": []}
    rows_pressure_pump = {"x": [], "y": [], "series": []}
    rows_pressure = {"x": [], "y": [], "series": []}
    for i in range(start, end):
        x_ts = build_rows(i)
        rows_oxygen["x"].extend([x_ts, x_ts, x_ts, x_ts])
        rows_oxygen["y"].extend([
            float(data.get("ox_desired", [0.0])[i] if len(data.get("ox_desired", [])) > i else 0.0),
            float(data.get("ox_meas1", [0.0])[i] if len(data.get("ox_meas1", [])) > i else 0.0),
            float(data.get("ox_meas2", [0.0])[i] if len(data.get("ox_meas2", [])) > i else 0.0),
            float(data.get("ox_meas3", [0.0])[i] if len(data.get("ox_meas3", [])) > i else 0.0),
        ])
        rows_oxygen["series"].extend(["Desired", "Measured 1", "Measured 2", "Measured 3"])

        rows_flow["x"].extend([x_ts, x_ts])
        rows_flow["y"].extend([
            float(data.get("flow_desired", [0.0])[i] if len(data.get("flow_desired", [])) > i else 0.0),
            float(data.get("flow_actual", [0.0])[i] if len(data.get("flow_actual", [])) > i else 0.0),
        ])
        rows_flow["series"].extend(["Desired", "Actual"]) 

        rows_pressure_pump["x"].extend([x_ts, x_ts])
        rows_pressure_pump["y"].extend([
            float(data.get("press_pump_desired", [0.0])[i] if len(data.get("press_pump_desired", [])) > i else 0.0),
            float(data.get("press_pump_actual", [0.0])[i] if len(data.get("press_pump_actual", [])) > i else 0.0),
        ])
        rows_pressure_pump["series"].extend(["Desired", "Actual"]) 

        rows_pressure["x"].extend([x_ts, x_ts])
        rows_pressure["y"].extend([
            float(data.get("pressure_desired", [0.0])[i] if len(data.get("pressure_desired", [])) > i else 0.0),
            float(data.get("pressure_actual", [0.0])[i] if len(data.get("pressure_actual", [])) > i else 0.0),
        ])
        rows_pressure["series"].extend(["Desired", "Actual"]) 

    if charts.get("oxygen"):
        charts["oxygen"].add_rows(pd.DataFrame(rows_oxygen))
    if charts.get("flow"):
        charts["flow"].add_rows(pd.DataFrame(rows_flow))
    if charts.get("pressure_pump"):
        charts["pressure_pump"].add_rows(pd.DataFrame(rows_pressure_pump))
    if charts.get("pressure"):
        charts["pressure"].add_rows(pd.DataFrame(rows_pressure))
    st.session_state._pidc_painted = end


_collector()
_render_tick()


