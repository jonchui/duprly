# 🚀 Install Homebrew and oh-my-zsh

## Quick Install

Run this in your terminal:

```bash
./install_brew_and_zsh.sh
```

This will:
1. Install Homebrew (you'll be prompted for your password)
2. Add Homebrew to your PATH
3. Install oh-my-zsh
4. Set zsh as your default shell

## Manual Install (if script doesn't work)

### Step 1: Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**For Apple Silicon Macs**, add Homebrew to PATH:
```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

**For Intel Macs**, add Homebrew to PATH:
```bash
echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/usr/local/bin/brew shellenv)"
```

### Step 2: Install oh-my-zsh

```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
```

### Step 3: Verify Installation

```bash
# Check Homebrew
brew --version

# Check zsh
zsh --version

# Check if zsh is default
echo $SHELL
```

## After Installation

1. **Restart your terminal** (or run `source ~/.zshrc`)

2. **Install Python 3.11 and set up MCP:**
   ```bash
   brew install python@3.11
   ./setup_mcp.sh
   ```

## Troubleshooting

### "Permission denied" during Homebrew install
- Make sure you're an Administrator on your Mac
- You'll be prompted for your password during installation

### "brew: command not found" after install
- Restart your terminal
- Or run: `source ~/.zprofile`
- Check if Homebrew is in `/opt/homebrew/bin/brew` (Apple Silicon) or `/usr/local/bin/brew` (Intel)

### oh-my-zsh not working
- Make sure zsh is installed: `which zsh`
- Set zsh as default: `chsh -s $(which zsh)`
- Restart terminal

