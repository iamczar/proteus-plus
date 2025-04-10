module.exports = {
  apps: [
    {
      name: "streamlit-app",
      script: "./venv/Scripts/python.exe",
      args: "-m streamlit run main.py",
      cwd: __dirname + "/proteus-ui",
      autorestart: false
    },
    {
      name: "software-update",
      script: "./venv/Scripts/python.exe",
      args: "-m software_update",
      cwd: __dirname,
      autorestart: false
    }
  ]
};
