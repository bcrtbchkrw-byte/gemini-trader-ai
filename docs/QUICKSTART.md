# Quick Start - Installation Guide

## 📦 Installation

### 1. Clone & Setup
```bash
git clone <repo-url>
cd gemini-trader-ai
./setup.sh
```

**What setup.sh does:**
- Creates/activates virtual environment
- Installs all dependencies from requirements.txt
- **Runs dependency check automatically**
- Verifies scipy and VannaCalculator work

### 2. Manual Installation
```bash
# Create venv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python check_dependencies.py
```

### 3. Expected Output
```
============================================================
✅ scipy                  1.11.4
✅ numpy                  1.24.3
✅ pandas                 2.0.3
... (all packages)

Installed: 12/12

Critical Component Tests:
✅ scipy: scipy working (norm.pdf(0) = 0.3989)
✅ VannaCalculator: VannaCalculator working

============================================================
✅ All dependencies OK - System ready!
```

## ⚠️ If Dependencies Missing

**Error:**
```
❌ scipy                     MISSING
❌ Dependency check FAILED
```

**Fix:**
```bash
pip install -r requirements.txt

# Or specific package:
pip install scipy numpy
```

## 🔧 Configuration

### 1. Create .env file
```bash
cp .env.example .env
nano .env
```

### 2. Add API keys
```bash
GEMINI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
NEWS_API_KEY=your_key_here

# IBKR connection
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1
```

## ✅ Verify Installation

```bash
# Check all dependencies
python check_dependencies.py

# Should show:
# ✅ All dependencies OK - System ready!
```

## 🚀 Run

### Auto-Scheduler (Recommended)
```bash
# Set in .env:
AUTO_PREMARKET_SCAN=true

# Run:
python main.py
```

### Continuous Daemon
```bash
./run_scheduler.sh
```

### Manual Mode
```bash
# Set in .env:
AUTO_PREMARKET_SCAN=false

# Run:
python main.py
```

## 📝 Critical Dependencies

**For Vanna Calculation:**
- scipy >= 1.11.0 ⚠️ REQUIRED
- numpy >= 1.24.0 ⚠️ REQUIRED
- py_vollib (optional, but recommended)

**For Trading:**
- ib_insync
- google-generativeai
- anthropic

**Verified by:** `check_dependencies.py`

---

**Status:** Setup script will fail if dependencies missing ✅
