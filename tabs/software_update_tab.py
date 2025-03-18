from nicegui import ui
import asyncio

def load_software_update_tab():
    with ui.tab_panel('f'):  # Must match the tab key in main.py
        with ui.row().classes('w-full justify-between p-4 gap-8'):  
            # Column 1: "Check for Updates" Button (Square)
            with ui.column().classes('items-center'):
                ui.button("Check for Updates", on_click=check_for_updates, color="blue") \
                    .style("width: 100px; height: 100px; font-size: 16px;")
                    
            # Column 2: Proteus Plus, Alpha+ Software, Alpha+ Firmware (stacked, square)
            with ui.column().classes('items-start gap-2'):
                ui.button("Proteus Plus", on_click=check_for_updates, color="blue") \
                    .style("width: 100px; height: 100px;")
                ui.button("Alpha+ Software", on_click=check_for_updates, color="blue") \
                    .style("width: 100px; height: 100px;")
                ui.button("Alpha+ Firmware", on_click=check_for_updates, color="blue") \
                    .style("width: 100px; height: 100px;")

            # Column 3: Log Output:
            # Column 3: Plain Box (No Cursor, No Interaction)
            with ui.column().classes('items-start'):
                ui.html('''
                    <div style="
                        width: 75vw;   
                        height: 80vh;  
                        min-width: 150px;
                        min-height: 150px;
                        border: 3px solid black; 
                        background-color: white; 
                        display: flex;  
                        align-items: center;  
                        justify-content: center;  
                        position: relative;
                    ">
                        <img id="update-icon" src="/ui_images/anticlockwise-arrow.png" style="
                            width: 100px; 
                            height: 100px;
                            display: none;  /* Initially hidden */
                        ">
                    </div>
                ''')


# Placeholder functions (you can replace them with real update logic)
async def check_for_updates():
    show_spinner()
    start_spinner()
    await asyncio.sleep(3)  # Wait 3 seconds (non-blocking)
    stop_spinner()
    hide_spinner()

    
def start_spinner():
    ui.run_javascript("""
        let icon = document.getElementById('update-icon');
        if (!icon) return;  // Ensure the icon exists
        icon.style.animation = 'rotateAntiClockwise 1s linear infinite';

        // Add keyframes dynamically
        let styleSheet = document.styleSheets[0];
        let keyframes = `
            @keyframes rotateAntiClockwise {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(-360deg); } /* Ensures continuous anti-clockwise rotation */
            }
        `;

        let rules = Array.from(styleSheet.cssRules).map(rule => rule.cssText);
        if (!rules.includes(keyframes)) {
            styleSheet.insertRule(keyframes, styleSheet.cssRules.length);
        }
    """)


def stop_spinner():
    ui.run_javascript("""
        let icon = document.getElementById('update-icon');
        if (!icon) return;  // Ensure the icon exists
        icon.style.animation = ''; // Removes the spinning animation
    """)

def show_spinner():
    """Shows the spinner image inside the plain box."""
    ui.run_javascript("""
        let icon = document.getElementById('update-icon');
        if (icon) {
            icon.style.display = 'block';  // Make it visible
        }
    """)
    
def hide_spinner():
    """Hides the spinner image inside the plain box."""
    ui.run_javascript("""
        let icon = document.getElementById('update-icon');
        if (icon) {
            icon.style.display = 'none';  // Hide it
        }
    """)


def download_update():
    print("Downloading update...")

def install_update():
    print("Installing update...")
