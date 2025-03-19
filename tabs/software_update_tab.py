from nicegui import ui
import asyncio
import os
import requests

VERSION_FILE = "version.txt"  # Local version file
UPDATE_URL = "https://raw.githubusercontent.com/iamczar/proteus-plus/master/version.txt"
ZIP_URL = "https://github.com/iamczar/proteus-plus/archive/refs/tags/v1.0.zip"

GITHUB_API_RELEASES = "https://api.github.com/repos/iamczar/proteus-plus/releases/latest"

# Define version files and update URLs for each software
SOFTWARES = {
    "Proteus": {
        "version_file": "protues_version.txt",
        "update_url": "https://raw.githubusercontent.com/iamczar/proteus-plus/master/protues_version.txt",
        "zip_url": "https://github.com/iamczar/proteus-plus/archive/refs/tags/v1.0.zip",
    },
    "Alpha+ Software": {
        "version_file": "alpha_software_version.txt",
        "update_url": "https://raw.githubusercontent.com/iamczar/alpha-plus-software/master/version.txt",
        "zip_url": "https://github.com/iamczar/alpha-plus-software/archive/refs/tags/v1.0.zip",
    },
    "Alpha+ Firmware": {
        "version_file": "alpha_firmware_version.txt",
        "update_url": "https://raw.githubusercontent.com/iamczar/alpha-plus-firmware/master/version.txt",
        "zip_url": "https://github.com/iamczar/alpha-plus-firmware/archive/refs/tags/v1.0.zip",
    }
}





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
                        <!-- Top-left label -->
                        <span id="protues-update-status" style="
                            position: absolute;
                            top: 10px; 
                            left: 10px; 
                            font-size: 16px; 
                            font-weight: bold;
                            color: black;
                    "></span>
                        
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
    
    await check_updates_for_protues()
    # await check_updates_for_alpha_plus_software()
    # await check_updates_for_alpha_plus_firmware()
    
    await asyncio.sleep(1)  # Wait 3 seconds (non-blocking)
    stop_spinner()
    hide_spinner()
    
async def check_updates_for_protues():
    try:
        latest_version = get_latest_version_of_proteus(SOFTWARES["Proteus"]["update_url"])
        current_version = get_current_version_of_proteus(SOFTWARES["Proteus"]["version_file"])
        
        print(f"latest_version: {latest_version}")
        print(f"current_version: {current_version}")

        if latest_version and latest_version > current_version:
            msg = f"New version of Protues Plus is available :  {latest_version}"
            print(msg)
            proteus_update_status(msg)
        else:
            msg = "Proteus is up to date."
            print(msg)
            proteus_update_status(msg)
    except Exception as e:
        print(f"Error checking updates: {e}")
    
    
def get_current_version_of_proteus(version_file):
    """Reads the current version from the local version.txt file."""
    if os.path.exists(version_file):
        with open(version_file, "r") as f:
            return f.read().strip()
    return "0.0"  # Default version if file doesn't exist

def get_latest_version_of_proteus(update_url):
    """Fetches the latest version from GitHub."""
    try:
        response = requests.get(update_url)
        if response.status_code == 200:
            return response.text.strip()
    except Exception as e:
        print(f"Failed to fetch latest version: {e}")
    return None

    
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
    
def proteus_update_status(msg):
    """Updates the UI label inside the white box."""
    ui.run_javascript(f"""
        let statusElement = document.getElementById('protues-update-status');
        if (statusElement) {{
            statusElement.textContent = "{msg}";
        }}
    """)


def download_update():
    print("Downloading update...")

def install_update():
    print("Installing update...")
