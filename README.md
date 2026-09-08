
Environment Deployment Specification
Planetary Defence Cybersecurity — GMAT/Python Pipeline


**1. Deployment Objective**
Provision a clean, isolated, and reproducible computational environment for the Integrity Assurance in Planetary Defence research pipeline.
The environment is intended to support Python-based data acquisition, astronomical data processing, analysis, visualisation, and GMAT-based simulation workflows.
The deployment should be performed in a dedicated project workspace with sufficient storage and system resources so that the workload does not interfere with unrelated applications, projects, or system components.


**2. Supported Platforms**
The environment should be prepared for:

"macOS — native execution"
"Linux — native execution"

The macOS setup script should be used on macOS. A Linux-specific setup script should be maintained separately rather than executing the macOS configuration unchanged.
No Linux virtual machine is required for the macOS deployment.


**3. Project Workspace**
The current macOS configuration expects the project workspace at:

$HOME/Demon/GMAT/
Before execution, verify that this directory exists and is accessible:

_ls -ld "$HOME/Demon/GMAT/"_
The workspace should have:

Sufficient free storage
Read/write permissions
Stable filesystem access
Appropriate I/O performance
Separation from unrelated workloads where practical
The project directory should be considered the root workspace for the computational pipeline.


**4. Storage Provisioning**
The complete workload may become storage-intensive even though the initial Python environment installation is relatively small.
Provision sufficient storage for:

Python virtual environment
Python package cache
Astronomical observation data
MPC/JPL datasets
CSV/JSON files
Intermediate processing data
GMAT simulation outputs
Generated plots and figures
Logs
Experimental results
Backups and reproducibility artifacts
Do not store large experimental outputs inside the venv/ directory.
Recommended structure:

Demon/
└── GMAT/
    ├── venv/
    ├── scripts/   [download Full "scripts/"  inside Here]
        ├── 00_batch_pipeline_50objects_fixed.py
        ├── 00e_fetch_150_nobs.py
        ├── 04_gmat_orbital_impact.py
        ├── 05_generate_charts.py
    ├── data/
    ├── results/
    ├── logs/
    ├── simulations/
        ├── 04_gmat_orbital_impact_v2.py
    └── outputs/
This keeps the disposable Python environment separate from research data and generated artifacts.

**5. Python Environment**
The deployment script detects the first available python3 executable:
PYTHON_BIN=$(command -v python3)
The detected interpreter is then used to create a project-local virtual environment:

"$PYTHON_BIN" -m venv venv
The resulting environment is activated with:

source venv/bin/activate
This isolates the project's Python dependencies from the host system and other Python projects.


**6. Required Python Dependencies**
The following packages are provisioned inside the virtual environment:

requests
pandas
numpy
matplotlib
astropy
astroquery
The installation process also upgrades pip before installing the dependencies.
After installation, the script performs an import-level verification to ensure that all required modules can be loaded successfully.


**7. Clean Environment Rebuild**
The setup script intentionally removes an existing:

venv/
before creating a new environment.
Therefore:

Do not store research data, datasets, scripts, results, or other persistent project material inside venv/.
The venv/ directory should be considered disposable and reproducible.
If the environment becomes corrupted, it can be safely recreated without affecting the research data stored elsewhere in the project workspace.

**8. GMAT Configuration**
The deployment checks for GMAT R2026a at:

/Applications/GMAT R2026a/bin/GmatConsole
If GMAT is installed at another location, configure:

export GMAT_CONSOLE="/path/to/your/GmatConsole"
before executing the relevant pipeline.
GMAT should remain independently installed from the Python virtual environment.

**9. Network Requirements**
An active network connection may be required during environment provisioning and subsequent research execution.
The system may need network access for:

Python package installation
Astronomical data retrieval
MPC services
JPL services/APIs
Other explicitly configured research data sources
Network access should therefore be verified before running data-fetching components.

**10. Resource Isolation**
Select an appropriate location and execution environment for the mission.
The workload should not unnecessarily compete with:

Critical system processes
Other computational workloads
Unrelated development environments
User data
Other research projects
Storage-intensive applications
For large runs, monitor:

CPU utilisation
RAM utilisation
Disk capacity
Disk I/O
Temporary storage
Network utilisation
The objective is to prevent the research pipeline from unintentionally degrading the operation of other applications or exhausting system resources.


**11. Pre-Execution Validation**
Before starting the main pipeline, confirm:

[✓] Correct operating system
[✓] python3 available
[✓] Correct Python interpreter detected
[✓] Project workspace exists
[✓] Project workspace is writable
[✓] Adequate storage available
[✓] Virtual environment created
[✓] Virtual environment activated
[✓] pip operational
[✓] Required dependencies installed
[✓] Required dependencies successfully imported
[✓] GMAT R2026a detected/configured
[✓] Network connectivity available
[✓] Research data directories separated from venv/
[✓] System resources sufficient for the intended workload
Only after these checks have passed should the data-fetching, processing, analysis, and GMAT simulation workflows be initiated.
12. Standard Startup Procedure
For a new terminal session:

cd "$HOME/Demon/GMAT/"
source venv/bin/activate
Then verify:

which python3
python3 --version
The Python executable should resolve to the project-local environment:

$HOME/Demon/GMAT/venv/bin/python3
The environment is then ready for the project scripts and pipeline.
Deployment Architecture
The intended execution architecture is:
macOS / Linux Host
↓
Dedicated $HOME/Demon/GMAT/ Workspace
↓
Project-Local Python Virtual Environment
↓
Scientific & Astronomy Dependencies
↓
MPC / JPL Data Acquisition
↓
Python Processing & Analysis
↓
GMAT Simulation
↓
Experimental Results / Logs / Figures
↓
Research Outputs


**Final Requirement**
Before initiating the mission and associated computational tasks, ensure that the selected project location has adequate storage, appropriate filesystem permissions, sufficient computational resources, and proper isolation from unrelated workloads.
The environment should be treated as a controlled research execution environment, with disposable dependencies separated from persistent research data and experimental outputs.
