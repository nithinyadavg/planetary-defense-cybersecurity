#!/bin/bash
# ============================================================
# One-shot Python environment setup — native macOS, no Homebrew
# Python juggling, no Linux VM.
#
# Dissertation / Conference Paper: Integrity Assurance in Planetary Defence
# Author: Nithin Yadav Gopinath (C5003001)
# MSc Cybersecurity, Sheffield Hallam University
# ============================================================
set -e  # stop immediately on any real error, rather than limping on

echo "============================================================"
echo "Setting up a clean, self-contained Python environment"
echo "============================================================"

# Use whichever python3 is already on PATH (Homebrew's or Apple's) —
# we don't fight over which one is 'the' python, we just build an
# isolated venv on top of it so nothing else on your Mac is touched.
PYTHON_BIN=$(command -v python3)
if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: no python3 found on PATH. Install it first (e.g. 'brew install python@3.14') and re-run this script."
    exit 1
fi
echo "Using: $PYTHON_BIN ($($PYTHON_BIN --version))"

# Create the venv INSIDE the dissertation project folder, so it's
# self-contained and easy to delete/recreate if anything goes wrong.
PROJECT_DIR="$HOME/ME/SHU AtZ/Demon/GMAT/dissertation"
if [ ! -d "$PROJECT_DIR" ]; then
    echo "ERROR: expected project folder not found at:"
    echo "  $PROJECT_DIR"
    echo "Edit PROJECT_DIR at the top of this script if your path differs, then re-run."
    exit 1
fi
cd "$PROJECT_DIR"
echo "Project folder: $PROJECT_DIR"

# Fresh venv every time this script runs — avoids the 'half-broken from
# three sessions ago' venv problem we kept hitting.
if [ -d "venv" ]; then
    echo "Removing existing venv/ for a clean rebuild..."
    rm -rf venv
fi

"$PYTHON_BIN" -m venv venv
source venv/bin/activate
echo "venv active: $(which python3)"

echo ""
echo "Upgrading pip..."
python3 -m pip install --upgrade pip --quiet

echo ""
echo "Installing all required packages in one shot..."
python3 -m pip install --quiet \
    requests \
    pandas \
    numpy \
    matplotlib \
    astropy \
    astroquery

echo ""
echo "============================================================"
echo "Verifying installation"
echo "============================================================"
python3 -c "
import requests, pandas, numpy, matplotlib, astropy, astroquery
print('requests   :', requests.__version__)
print('pandas     :', pandas.__version__)
print('numpy      :', numpy.__version__)
print('matplotlib :', matplotlib.__version__)
print('astropy    :', astropy.__version__)
print('astroquery :', astroquery.__version__)
"

echo ""
echo "============================================================"
echo "GMAT check"
echo "============================================================"
GMAT_DEFAULT="/Applications/GMAT R2026a/bin/GmatConsole"
if [ -f "$GMAT_DEFAULT" ]; then
    echo "Found GMAT at default location: $GMAT_DEFAULT"
else
    echo "WARNING: GMAT not found at $GMAT_DEFAULT"
    echo "If yours is installed elsewhere, run this before the pipeline script:"
    echo '  export GMAT_CONSOLE="/path/to/your/GmatConsole"'
fi

echo ""
echo "============================================================"
echo "DONE. Environment ready."
echo "============================================================"
echo "Every time you open a new terminal for this project, run:"
echo "  cd \"$PROJECT_DIR\""
echo "  source venv/bin/activate"
echo ""
echo "Then you're ready to run the fetch/pipeline scripts."
