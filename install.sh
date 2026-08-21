#!/bin/bash
# Lex Installer for Linux (One-Click)
# This script automates the installation of 'lex' into a managed virtual environment.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Lex Installation...${NC}"

# 1. Detect OS and Install Dependencies
if [ -f /etc/debian_version ]; then
    echo -e "${BLUE}📦 Detecting Debian/Ubuntu... ensuring python3-venv is installed.${NC}"
    # Check if python3-venv is installed, if not, attempt to install
    if ! dpkg -l | grep -q "python3.*-venv"; then
        echo -e "${BLUE}Installing python3-venv (requires sudo)...${NC}"
        sudo apt update -qq && sudo apt install -y -qq python3-venv git
    fi
elif [ -f /etc/fedora-release ]; then
    echo -e "${BLUE}📦 Detecting Fedora...${NC}"
    sudo dnf install -y -q python3-virtualenv git
fi

# 2. Setup Directories
INSTALL_DIR="$HOME/.local/share/lex"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# 3. Create Virtual Environment
echo -e "${BLUE}🛠️  Creating isolated Python environment in $INSTALL_DIR...${NC}"
python3 -m venv "$INSTALL_DIR/venv"

# 4. Install Lex from GitHub
echo -e "${BLUE}📥 Installing Lex from GitHub...${NC}"
"$INSTALL_DIR/venv/bin/pip" install -q git+https://github.com/elcafe7/lex.git

# 5. Create Symlink
echo -e "${BLUE}🔗 Linking binary to $BIN_DIR/lex...${NC}"
ln -sf "$INSTALL_DIR/venv/bin/lex" "$BIN_DIR/lex"

# 6. Ensure PATH is set
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    if ! grep -q "$PATH_LINE" "$HOME/.bashrc"; then
        echo -e "${BLUE}📝 Adding $BIN_DIR to PATH in .bashrc...${NC}"
        echo "" >> "$HOME/.bashrc"
        echo "# Lex CLI path" >> "$HOME/.bashrc"
        echo "$PATH_LINE" >> "$HOME/.bashrc"
        echo -e "${GREEN}✅ PATH updated. Please run 'source ~/.bashrc' or restart your terminal.${NC}"
    fi
fi

echo -e "${GREEN}✨ Lex installed successfully!${NC}"
echo -e "Try running: ${BLUE}lex --help${NC}"
