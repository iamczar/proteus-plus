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
      name: "module-controller",
      script: "./venv/Scripts/python.exe",
      args: "-m module_controller",
      cwd: __dirname,
      autorestart: true,
      max_restarts: 5
    }
  ]
};
