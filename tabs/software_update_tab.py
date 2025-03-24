from nicegui import ui
import asyncio
import os
import requests
import zipfile

GITHUB_API_RELEASES = "https://api.github.com/repos/iamczar/proteus-plus/releases/latest"

# Define version files and update URLs for each software
SOFTWARES = {
    "Proteus": {
        "version_file": "proteus_version.txt",
        "update_url": "https://raw.githubusercontent.com/iamczar/proteus-plus/master/proteus_version.txt",
        "zip_url": "https://github.com/iamczar/proteus-plus/archive/refs/tags/",
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

# Path to the Proteus update page HTML file
PROTEUS_UPDATE_PAGE = "tabs/proteus_software_update_page.html"
CHECK_FOR_UPDATE_PAGE = "tabs/check_for_update.html"

# Store button references globally or in outer scope
button_refs = {}

def highlight_selected_button(selected_key):
    for key, btn in button_refs.items():
        btn.props('color=green' if key == selected_key else 'color=blue')

def load_software_update_tab():
    with ui.tab_panel('f'):  # Must match the tab key in main.py
        with ui.row().classes('w-full justify-between p-4 gap-8'):  
            # Column 1: "Check for Updates" Button (Square)
            with ui.column().classes('items-center'):
                 button_refs["check-for-update"] = ui.button(
                     "Check for Updates", 
                     on_click=lambda:check_for_updates()
                    ).style("width: 100px; height: 100px; font-size: 16px;")
                    
            # Column 2: Proteus Plus, Alpha+ Software, Alpha+ Firmware (stacked, square)
            with ui.column().classes('items-start gap-2'):
                button_refs["proteus"] = ui.button(
                    "Proteus Plus", 
                    on_click=lambda: [highlight_selected_button("proteus"), load_proteus_update_page()]
                ).style("width: 100px; height: 100px;")

                button_refs["alpha_software"] = ui.button(
                    "Alpha+ Software", 
                    on_click=lambda: highlight_selected_button("alpha_software")
                ).style("width: 100px; height: 100px;")

                button_refs["alpha_firmware"] = ui.button(
                    "Alpha+ Firmware", 
                    on_click=lambda: highlight_selected_button("alpha_firmware")
                ).style("width: 100px; height: 100px;")

            # Column 3: Log Output:
            # Column 3: Plain Box (No Cursor, No Interaction)
            with ui.column().classes('items-start'):
                with ui.element('div').props('id=software-check-update-page').style('''
                    width: 75vw;
                    height: 80vh;
                    min-width: 150px;
                    min-height: 150px;
                    border: 3px solid black;
                    background-color: white;
                    position: relative;
                    overflow: auto;
                '''):
                    # 🔁 Your dynamic content placeholder
                    ui.html('<div id="software-dynamic-content" style="width: 100%; height: 100%;"></div>')

                    # 🟩 Button 1 (center bottom)
                    ui.button("Update", on_click=handle_update_click_proteus, color="green").style('''
                        position: absolute;
                        bottom: 20px;
                        left: 50%;
                        transform: translateX(-50%);
                        width: 100px;
                        height: 100px;
                        font-weight: bold;
                        border: 2px solid black;
                    ''')

                    # 🟩 Button 2 (bottom-right)
                    ui.button("Restart", on_click=handle_restart_click_proteus, color="green").style('''
                        position: absolute;
                        bottom: 20px;
                        right: 20px;
                        width: 100px;
                        height: 100px;
                        font-weight: bold;
                        border: 2px solid black;
                    ''')

            
            

# Placeholder functions (you can replace them with real update logic)
async def check_for_updates():
    
    highlight_selected_button("check-for-update")
    html_content = load_html_content(CHECK_FOR_UPDATE_PAGE)
    
    js_command = f"""
        document.getElementById('software-dynamic-content').innerHTML = `{html_content}`;
    """
    ui.run_javascript(js_command)
    
    await show_spinner()
    await start_spinner()
    
    
    await check_updates_for_protues()
    # await check_updates_for_alpha_plus_software()
    # await check_updates_for_alpha_plus_firmware()
    
    await asyncio.sleep(1)  # Wait 3 seconds (non-blocking)
    await stop_spinner()
    await hide_spinner()
    
async def check_updates_for_protues():
    try:
        latest_version = get_latest_version_of_proteus(SOFTWARES["Proteus"]["update_url"])
        current_version = get_current_version_of_proteus(SOFTWARES["Proteus"]["version_file"])
        
        print(f"latest_version: {latest_version}")
        print(f"current_version: {current_version}")

        if latest_version and latest_version > current_version:
            msg = f"New version of Protues Plus is available :  {latest_version}"
            proteus_update_status(msg)
        else:
            msg = f"Proteus is up to date. {current_version}"
            proteus_update_status(msg)
    except Exception as e:
        print(f"Error checking updates: {e}")
    
    
def get_current_version_of_proteus(version_file):
    """Reads the current version from the local version.txt file."""
    try:
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                return f.read().strip()
        else:
            print("file does not exist")
            return "0.0"
    except Exception as e:
        print(e)
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

    
async def start_spinner():
    ui.run_javascript("""
        const icon = document.getElementById('update-icon');
        console.log('[SPINNER] Found icon:', icon);
        if (!icon) return;

        icon.style.animation = 'rotateAntiClockwise 1s linear infinite';

        const styleSheet = document.styleSheets[0];
        const keyframes = `
            @keyframes rotateAntiClockwise {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(-360deg); }
            }
        `;

        const rules = Array.from(styleSheet.cssRules || []);
        if (!rules.find(rule => rule.name === 'rotateAntiClockwise')) {
            styleSheet.insertRule(keyframes, styleSheet.cssRules.length);
        }
    """)


async def stop_spinner():
    ui.run_javascript("""
        let icon = document.getElementById('update-icon');
        if (!icon) return;  // Ensure the icon exists
        icon.style.animation = ''; // Removes the spinning animation
    """)

async def show_spinner():
    """Shows the spinner image inside the plain box."""
    ui.run_javascript("""
        let icon = document.getElementById('update-icon');
        if (icon) {
            icon.style.display = 'block';  // Make it visible
        }
    """)
    
async def hide_spinner():
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
    
async def update_html_text_by_id(element_id: str, new_text: str):
    """Dynamically update the text content of an element by ID via JavaScript."""
    ui.run_javascript(f"""
        const el = document.getElementById('{element_id}');
        if (el) {{
            el.textContent = `{new_text}`;
        }}
    """)

def load_html_content(file_path):
    """Loads the HTML content from a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        print(f"Error loading HTML file: {e}")
        return "<p>Error loading content</p>"

# ✅ **Function to Load the Proteus Update Page**
def load_proteus_update_page():
    """Loads the Proteus update page dynamically into the white box and updates version info."""
    html_content = load_html_content(PROTEUS_UPDATE_PAGE)

    current_version = get_current_version_of_proteus(SOFTWARES["Proteus"]["version_file"])
    latest_version = get_latest_version_of_proteus(SOFTWARES["Proteus"]["update_url"])

    js_command = f"""
        document.getElementById('software-dynamic-content').innerHTML = `{html_content}`;

        setTimeout(() => {{
            const current = document.getElementById('proteus-current-version');
            const latest = document.getElementById('protues-latest-version');
            if (current) current.textContent = 'Current Version : {current_version}';
            if (latest) latest.textContent = 'Latest Version : {latest_version}';
        }}, 50);
    """
    ui.run_javascript(js_command)

def install_update():
    print("Installing update...")
    
async def download_proteus_update(zip_url: str, save_path='proteus_update.zip'):
    """Downloads the Proteus update zip file from the provided URL."""
    try:
        response = requests.get(zip_url)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            msg = f"Downloaded update to {save_path}"
            await update_html_text_by_id('update-message-proteus',msg)
            return save_path
        else:
            msg = f"Failed to download update: {response.status_code}"
            print(msg)
            await update_html_text_by_id('update-message-proteus',msg)
            
            
    except Exception as e:
        msg = f"Error downloading update: {e}"
        print(msg)
        await update_html_text_by_id('update-message-proteus',msg)
    return None

async def extract_update(zip_path: str, extract_to='.'):
    """Extracts the zip file to the specified directory."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        print(f"Extracted update to {extract_to}")
        return True
    except Exception as e:
        print(f"Error extracting update: {e}")
        return False

async def on_update_click_proteus():
    
    latest_version = get_latest_version_of_proteus(SOFTWARES["Proteus"]["update_url"])
    # download the files
    zip_url_base = SOFTWARES["Proteus"]["zip_url"]
    zip_url = f"{zip_url_base}{latest_version}.zip"
    
    print(zip_url)
    
    zip_path = await download_proteus_update(zip_url)
    await asyncio.sleep(1) 
    if zip_path:
        msg = f"extracting {zip_path}..."
        await update_html_text_by_id('update-message-proteus',msg)
        await asyncio.sleep(1)
        success = await extract_update(zip_path, extract_to='.')
        if success:
            msg = "Update files extracted successfully!"
            print(msg)
            await update_html_text_by_id('update-message-proteus',msg)
        else:
            msg = "Failed to extract update files."
            print(msg)
            await update_html_text_by_id('update-message-proteus',msg)

def on_restart_click_proteus():
    print("Restart button clicked! on proteus")
    # Add restart logic (e.g., os.system('reboot') or similar)
    
async def handle_update_click_proteus():
    
    print("Update in progress...")
    await update_html_text_by_id('update-message-proteus',"Update in progress...")    
    await show_spinner()
    await start_spinner()
    await asyncio.sleep(1) 
    await on_update_click_proteus()
    await stop_spinner()
    await hide_spinner()
    return "OK"

async def handle_restart_click_proteus():
    on_restart_click_proteus()
    return "OK"
