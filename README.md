# Proteus+ Data Acquisition & Control System

## Overview

Proteus+ is a comprehensive data acquisition and control suite for laboratory equipment and experiments. It consists of:
- **Streamlit UI** (`proteus-ui/`): Web-based dashboard for visualization, control, and data management
- **Module Controller** (`module_controller/`): Python backend for hardware communication, MQTT messaging, and data processing
- **Experiment Framework**: Structured experiment definitions, sequence files, and automated data logging

The system uses MQTT for inter-process communication and supports serial device integration, real-time plotting, and automated data export.

## Repository Structure

```
proteus-plus/
├── proteus-ui/              # Streamlit web application
│   ├── main.py              # Main UI entry point
│   ├── pages/               # Multi-page UI modules
│   ├── services/            # UI business logic
│   ├── assets/              # Static assets (images, styles)
│   ├── requirements.txt     # UI Python dependencies
│   └── Dockerfile           # Docker container for UI
├── module_controller/       # Backend controller service
│   └── __main__.py          # Controller entry point
├── common/                  # Shared utilities and constants
├── experiments/             # Experiment definitions
├── sequence_files/          # Automated sequence configurations
├── data/                    # Logged data and exports
├── tools/                   # Helper scripts and utilities
├── tests/                   # Unit and integration tests
├── lem_software/            # LEM (Lab Equipment Manager) integration
├── software_update/         # Update and deployment scripts
├── requirements.txt         # Root-level Python dependencies
├── ecosystem.config.js      # PM2 process manager config (Windows)
└── setup-and-run.bat        # Windows setup script
```

## Prerequisites

### Required
- **Python 3.10+** (3.11 recommended)
- **pip** and **venv** (for virtual environments)

### Optional (Recommended)
- **PM2** (Node.js process manager) for production deployment on Windows
- **Docker** (for containerized UI deployment)
- **MQTT Broker** (e.g., Mosquitto) for inter-process messaging
- Serial device access permissions (Linux/WSL: `dialout` group)

## Quick Start (Local, Without PM2)

### 1. Create Virtual Environment
```bash
cd proteus-plus
python -m venv venv
```

### 2. Activate Virtual Environment
**Linux/WSL:**
```bash
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
.\venv\Scripts\activate.bat
```

### 3. Install Dependencies
```bash
# Root dependencies (module_controller)
pip install -r requirements.txt

# UI dependencies
pip install -r proteus-ui/requirements.txt
```

### 4. Start Module Controller (Backend)
In one terminal:
```bash
python -m module_controller
```

### 5. Start Proteus UI (Frontend)
In another terminal:
```bash
cd proteus-ui
streamlit run main.py
```

The UI will open automatically at `http://localhost:8501`.

## PM2 Managed Deployment (Windows Production)

PM2 provides automatic restarts, log management, and process monitoring.

### Prerequisites
Install Node.js and PM2:
```powershell
winget install OpenJS.NodeJS
npm install -g pm2
```

### First-Time Streamlit Initialization (skip email prompt)
On the **first run on a new machine**, initialize Streamlit interactively (so it can store your choice and won't prompt when run under PM2):

```powershell
cd proteus-plus
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r proteus-ui\requirements.txt

cd proteus-ui
streamlit run main.py
```

When prompted for an email, either enter one or just press **Enter** to leave it blank. After closing Streamlit (Ctrl+C), future runs via PM2 will start without blocking for input.

### Setup Virtual Environment (Windows)
```powershell
cd proteus-plus
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r proteus-ui\requirements.txt
```

### Start with PM2
From the `proteus-plus` root directory:
```powershell
pm2 start ecosystem.config.js
```

This starts two processes:
1. **streamlit-app**: Runs the Streamlit UI at `http://localhost:8501`
2. **module-controller**: Runs the backend controller with auto-restart

### PM2 Commands
```powershell
# View running processes
pm2 list

# View logs (real-time)
pm2 logs

# View logs for specific app
pm2 logs streamlit-app
pm2 logs module-controller

# Restart all
pm2 restart all

# Restart specific app
pm2 restart streamlit-app

# Stop all
pm2 stop all

# Delete all from PM2
pm2 delete all

# Save PM2 process list (persist across reboots)
pm2 save

# Setup PM2 startup (auto-start on boot)
pm2 startup
```

### PM2 Configuration (`ecosystem.config.js`)
```javascript
module.exports = {
  apps: [
    {
      name: "streamlit-app",
      script: "./venv/Scripts/python.exe",
      args: "-m streamlit run main.py",
      cwd: __dirname + "/proteus-ui",
      autorestart: false  // Streamlit handles its own restarts
    },
    {
      name: "module-controller",
      script: "./venv/Scripts/python.exe",
      args: "-m module_controller",
      cwd: __dirname,
      autorestart: true,
      max_restarts: 5
    }
  ]
};
```

## Docker Deployment (UI Only)

### Build Docker Image
```bash
cd proteus-ui
docker build -t proteus-ui:latest .
```

### Run Container
```bash
docker run -p 8501:8501 proteus-ui:latest
```

### Docker Compose (Optional)
If a `docker-compose.yml` is present:
```bash
docker-compose up -d
```

## Configuration

### MQTT Broker
The system uses MQTT for communication between the UI and controller.

**Install Mosquitto (Local Broker)**:
- **Windows**: Download from [mosquitto.org](https://mosquitto.org/download/)
- **Linux/WSL**:
  ```bash
  sudo apt install mosquitto mosquitto-clients
  sudo systemctl start mosquitto
  ```

**Default Settings**:
- Host: `localhost`
- Port: `1883`
- Topics: Defined in `common/`

### Serial Devices
The module controller communicates with hardware via serial ports.

**Linux/WSL Permissions**:
```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

**Windows**:
- Device Manager → Ports (COM & LPT) → Note COM port numbers
- Ensure no other software (e.g., Arduino IDE) is using the port

### Environment Variables (Optional)
You can override defaults with environment variables:
- `MQTT_BROKER` - MQTT broker address (default: `localhost`)
- `MQTT_PORT` - MQTT port (default: `1883`)
- `DATA_DIR` - Data logging directory (default: `./data`)

## Development

### Code Layout
- **`proteus-ui/main.py`**: Streamlit entry point, homepage
- **`proteus-ui/pages/`**: Multi-page Streamlit UI modules
  - Add new pages by creating `pages/your_page.py`
  - Streamlit auto-discovers and adds to sidebar
- **`proteus-ui/services/`**: Business logic, data processing
- **`module_controller/`**: Backend service, serial/MQTT communication
- **`experiments/`**: Experiment definitions (Python classes or YAML)
- **`sequence_files/`**: Automated sequence definitions

### Adding a New Experiment
1. Create experiment definition in `experiments/`
2. Add UI page in `proteus-ui/pages/` for control/visualization
3. Update `module_controller/` if new hardware commands needed
4. Test locally before deploying

### Running Tests
```bash
# Run all tests
pytest

# Run UI tests only
pytest proteus-ui/tests/

# Run with coverage
pytest --cov=module_controller --cov=proteus-ui
```

### Linting and Formatting
```bash
# Format with black
black .

# Lint with flake8
flake8 proteus-ui/ module_controller/

# Type checking with mypy
mypy module_controller/
```

## Data Management

### Data Storage
- **Logged Data**: `data/` directory
- **Export Formats**: CSV, Excel (`.xlsx`), JSON
- **Plots**: PNG, SVG, interactive HTML (Plotly)

### Data Export
Use the UI:
1. Navigate to the relevant experiment page
2. Select data range and parameters
3. Click **Export** → Choose format

Or programmatically:
```python
from proteus-ui.services.data_exporter import DataExporter

exporter = DataExporter()
exporter.export_to_csv("experiment_001", "output.csv")
```

## Troubleshooting

### Streamlit Port Already in Use
```bash
# Kill process using port 8501
# Linux/WSL:
lsof -i :8501
kill -9 <PID>

# Windows (PowerShell):
netstat -ano | findstr :8501
taskkill /PID <PID> /F
```

Or use a different port:
```bash
streamlit run main.py --server.port 8502
```

### Module Controller Not Connecting to MQTT
- Check MQTT broker is running: `mosquitto -v` (Linux) or Task Manager (Windows)
- Verify `MQTT_BROKER` and `MQTT_PORT` settings
- Check firewall rules for port 1883

### Serial Device Not Found
- **List devices**:
  - Linux/WSL: `ls /dev/tty*`
  - Windows: Device Manager → Ports
- **Permissions**: Ensure user is in `dialout` group (Linux/WSL)
- **Driver Issues**: Reinstall USB-to-serial drivers (CH340, FTDI, etc.)

### Import Errors
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt -r proteus-ui/requirements.txt`
- Check Python version: `python --version` (should be 3.10+)

### PM2 Process Crashes on Startup
```powershell
# Check logs
pm2 logs --err

# Restart with verbose logging
pm2 restart all --update-env
```

Common causes:
- Virtual environment path incorrect in `ecosystem.config.js`
- Missing dependencies in venv
- Port conflicts (8501 already in use)

### Data Not Logging
- Check `data/` directory exists and is writable
- Verify MQTT messages are being published: `mosquitto_sub -t "#" -v`
- Check module controller logs for errors

## Updating Proteus+

### Pull Latest Changes
```bash
git pull origin main
```

### Update Dependencies
```bash
pip install --upgrade -r requirements.txt -r proteus-ui/requirements.txt
```

### Restart Services
**With PM2**:
```powershell
pm2 restart all
```

**Manual**:
- Stop running processes (Ctrl+C)
- Restart as per Quick Start

## Performance Tips

- **Use PM2** for production to leverage auto-restart and monitoring
- **Enable Streamlit caching**: Use `@st.cache_data` decorator in UI code
- **Optimize data queries**: Limit time ranges and data resolution
- **Monitor logs**: Regularly check PM2 logs for warnings
- **Database indexing**: If using a database backend, ensure proper indexing

## Security Considerations

- **Do not expose Streamlit publicly** without authentication (consider SSH tunneling or VPN)
- **MQTT Authentication**: Configure Mosquitto with username/password
- **Data Backups**: Regularly backup `data/` directory
- **Update Dependencies**: Keep Python packages up-to-date for security patches

## Advanced Configuration

### Custom MQTT Topics
Edit `common/mqtt_topics.py` to define custom topics.

### Custom Streamlit Themes
Create `.streamlit/config.toml` in `proteus-ui/`:
```toml
[theme]
primaryColor = "#1f77b4"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
font = "sans serif"
```

### Multi-Device Support
Run multiple module controllers on different ports/topics for parallel device management.

## Additional Resources

- [Streamlit Documentation](https://docs.streamlit.io/)
- [Paho MQTT Python Client](https://pypi.org/project/paho-mqtt/)
- [PM2 Documentation](https://pm2.keymetrics.io/docs/usage/quick-start/)
- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [Plotly Python Graphing Library](https://plotly.com/python/)

## Support and Contributing

For issues, feature requests, or contributions:
- Open an issue in the repository
- Contact the Proteus+ development team
- Review `CONTRIBUTING.md` (if available)

---

**Quick Start Checklist**:
- ✅ Python 3.10+ installed
- ✅ Virtual environment created and activated
- ✅ Dependencies installed
- ✅ MQTT broker running (if applicable)
- ✅ Module controller started
- ✅ Streamlit UI accessible at `http://localhost:8501`

Enjoy using Proteus+! 🔬📊
