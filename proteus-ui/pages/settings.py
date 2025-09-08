import streamlit as st
import subprocess
import os
import streamlit.components.v1 as components
import sys
from pathlib import Path
import json

st.set_page_config(page_title="Settings", layout="centered")
st.session_state["_current_page_key"] = "proteus_ui_settings"

st.title("Settings")

st.subheader("Proteus Services")

root = Path(__file__).resolve().parents[2]
ecosystem = root / "ecosystem.config.js"

col1, col2 = st.columns(2, gap="small")
with col1:
    if st.button("Restart Proteus", use_container_width=True):
        try:
            # Open a new tab which polls until the app is back, then close this tab
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
                  // Attempt to close this tab; fall back to navigating to about:blank
                  setTimeout(function(){
                    try {
                      window.open('', '_self');
                      window.close();
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
            # Delay the restart slightly so the client JS can render and execute
            if os.name == "nt":
                # Use ping for delay to avoid 'input redirection' errors with timeout
                subprocess.Popen(f"cmd /C ""ping -n 2 127.0.0.1 >NUL && pm2 restart \"{ecosystem}\"""", cwd=str(root), shell=True)
            else:
                subprocess.Popen(["bash", "-lc", f"sleep 1; pm2 restart {ecosystem}"], cwd=str(root))
            st.success("Restart signals scheduled.")
        except Exception as e:
            st.error(f"Failed to restart: {e}")
with col2:
    if st.button("Stop Proteus", type="secondary", use_container_width=True):
        try:
            # Attempt to close this browser tab/window (may be blocked by browser)
            components.html(
                """
                <script>
                setTimeout(function(){
                  try {
                    window.open('', '_self');
                    window.close();
                    setTimeout(function(){ location.replace('about:blank'); }, 300);
                  } catch (e) {
                    // Fallback: navigate away if the browser blocks close()
                    location.replace('about:blank');
                  }
                }, 500);
                </script>
                """,
                height=0,
            )
            # Delay the stop slightly so the client JS can render and execute
            if os.name == "nt":
                # Use ping for delay to avoid 'input redirection' errors with timeout
                subprocess.Popen("cmd /C \"ping -n 2 127.0.0.1 >NUL && pm2 stop all\"", cwd=str(root), shell=True)
            else:
                subprocess.Popen(["bash", "-lc", "sleep 1; pm2 stop all"], cwd=str(root))
            st.success("Stop signals scheduled.")
            st.caption("If the tab did not close automatically, you can close it manually.")
        except Exception as e:
            st.error(f"Failed to stop: {e}")

st.caption(f"ecosystem: {ecosystem}")
