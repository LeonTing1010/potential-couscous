#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define Virtual Environment Directory
VENV_DIR=".venv"
PYTHON_CMD="python3" # Default to python3

# --- Helper Functions ---

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to setup virtual environment and install dependencies
setup_venv() {
    echo "--- Setting up Virtual Environment (${VENV_DIR}) ---"
    if ! command_exists ${PYTHON_CMD}; then
        echo "Error: ${PYTHON_CMD} is not installed or not in PATH. Please install Python 3."
        exit 1
    fi

    if [ ! -d "${VENV_DIR}" ]; then
        echo "Creating virtual environment in ${VENV_DIR}..."
        ${PYTHON_CMD} -m venv "${VENV_DIR}"
        echo "Virtual environment created."
    else
        echo "Virtual environment '${VENV_DIR}' already exists."
    fi

    echo "Installing/Updating pip in venv..."
    "${VENV_DIR}/bin/pip" install --upgrade pip

    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies from requirements.txt..."
        "${VENV_DIR}/bin/pip" install -r requirements.txt
        echo "Dependencies installed."
    else
        echo "Warning: requirements.txt not found. Skipping dependency installation."
    fi
    echo "--- Virtual Environment setup complete ---"
}

# Function to run the scheduler's initial setup
run_scheduler_setup() {
    echo "--- Running Scheduler Initial Setup (populates target_apps.json) ---"
    if [ ! -f "${VENV_DIR}/bin/python" ]; then
        echo "Virtual environment not found or not set up. Please run './setup_and_run.sh setup' first."
        exit 1
    fi
    "${VENV_DIR}/bin/python" scheduler_script.py --setup
    echo "--- Scheduler Initial Setup finished ---"
}

# Function to start the scheduler
run_scheduler() {
    echo "--- Starting Scheduler ---"
    if [ ! -f "${VENV_DIR}/bin/python" ]; then
        echo "Virtual environment not found or not set up. Please run './setup_and_run.sh setup' first."
        exit 1
    fi
    "${VENV_DIR}/bin/python" scheduler_script.py
    echo "--- Scheduler finished or was interrupted ---"
}

# Function to run the reporting script
run_reporter() {
    echo "--- Running Reporting Script ---"
    if [ ! -f "${VENV_DIR}/bin/python" ]; then
        echo "Virtual environment not found or not set up. Please run './setup_and_run.sh setup' first."
        exit 1
    fi
    # Pass all arguments (after the 'report' command) to the reporting_script.py
    "${VENV_DIR}/bin/python" reporting_script.py "$@"
    echo "--- Reporting Script finished ---"
}

# Function to display help
show_help() {
    echo "DemandRadar Setup and Run Script"
    echo "--------------------------------"
    echo "Usage: ./setup_and_run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  setup         : Sets up the Python virtual environment and installs dependencies."
    echo "  init          : Runs the initial setup for the scheduler (populates target_apps.json)."
    echo "                  (Implicitly runs 'setup' if venv doesn't exist)."
    echo "  start         : Starts the main scheduler process."
    echo "                  (Implicitly runs 'setup' if venv doesn't exist)."
    echo "  scheduler     : Alias for 'start'."
    echo "  report [ARGS] : Runs the reporting script. Any additional arguments [ARGS]"
    echo "                  (e.g., --app_id com.example.app) are passed to reporting_script.py."
    echo "                  (Implicitly runs 'setup' if venv doesn't exist)."
    echo "  help          : Shows this help message."
    echo ""
    echo "Examples:"
    echo "  ./setup_and_run.sh setup       # Just setup the venv and dependencies"
    echo "  ./setup_and_run.sh init        # Populate target_apps.json"
    echo "  ./setup_and_run.sh start       # Start the scheduler"
    echo "  ./setup_and_run.sh report      # Run report for all apps"
    echo "  ./setup_and_run.sh report --app_id com.google.android.gm --limit 3"
    echo ""
}

# --- Main Script Logic ---

# Ensure requirements.txt exists for most operations that might implicitly trigger setup
# This check is a safeguard. setup_venv itself handles missing requirements.txt gracefully.
if [[ "$1" != "help" && "$1" != "" && "$1" != "setup" && ! -f "requirements.txt" ]]; then
    # If the command is not 'help' or 'setup' (which handles missing req.txt)
    # and requirements.txt is missing, then it's an issue for implicit setup.
    echo "Error: requirements.txt not found in the current directory."
    echo "Please ensure requirements.txt is present before running 'init', 'start', or 'report' commands,"
    echo "as they might attempt to set up the virtual environment."
    echo "Alternatively, run './setup_and_run.sh setup' manually which can proceed without requirements.txt (but will warn)."
    # exit 1 # Commented out to allow the specific command logic to proceed if it doesn't rely on implicit setup or if setup_venv handles it.
             # The individual run_ functions already check for venv python and exit if not found.
fi


if [ "$#" -eq 0 ]; then # No arguments
    show_help
    exit 0
fi

ACTION="$1"
# Shift arguments *after* the case statement decides if it needs them,
# or handle "$@" carefully in run_reporter. For simplicity, shift now.
shift 


case "${ACTION}" in
    setup)
        setup_venv
        ;;
    init)
        if [ ! -d "${VENV_DIR}" ]; then 
            echo "[INFO] Virtual environment not found for 'init'. Running setup first..."
            setup_venv # setup_venv will check for requirements.txt
        fi
        run_scheduler_setup
        ;;
    start|scheduler)
        if [ ! -d "${VENV_DIR}" ]; then 
            echo "[INFO] Virtual environment not found for '${ACTION}'. Running setup first..."
            setup_venv # setup_venv will check for requirements.txt
        fi
        run_scheduler
        ;;
    report)
        if [ ! -d "${VENV_DIR}" ]; then 
            echo "[INFO] Virtual environment not found for 'report'. Running setup first..."
            setup_venv # setup_venv will check for requirements.txt
        fi
        run_reporter "$@" # Pass remaining arguments (after 'report' was shifted)
        ;;
    help)
        show_help
        ;;
    *)
        echo "Error: Invalid command '${ACTION}'"
        show_help
        exit 1
        ;;
esac

exit 0
```
