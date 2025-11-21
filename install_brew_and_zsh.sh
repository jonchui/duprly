#!/bin/bash
# Install Homebrew and oh-my-zsh
# Run this script in your terminal (it will prompt for your password)

set -e

echo "🍺 Installing Homebrew..."
echo "=========================="
echo ""
echo "This will install Homebrew. You may be prompted for your password."
echo ""

# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Add Homebrew to PATH (for Apple Silicon Macs)
if [ -f /opt/homebrew/bin/brew ]; then
    echo ""
    echo "📝 Adding Homebrew to PATH..."
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
    echo "✅ Homebrew added to PATH"
elif [ -f /usr/local/bin/brew ]; then
    echo ""
    echo "📝 Adding Homebrew to PATH..."
    echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/usr/local/bin/brew shellenv)"
    echo "✅ Homebrew added to PATH"
fi

echo ""
echo "✅ Homebrew installed!"
echo ""

# Verify Homebrew
if command -v brew &> /dev/null; then
    brew --version
else
    echo "⚠️  Homebrew installed but not in PATH. Please restart your terminal or run:"
    echo "   source ~/.zprofile"
    exit 1
fi

echo ""
echo "🎨 Installing oh-my-zsh..."
echo "=========================="
echo ""

# Install oh-my-zsh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended

echo ""
echo "✅ oh-my-zsh installed!"
echo ""

# Verify zsh is default shell
if [ "$SHELL" != "/bin/zsh" ] && [ "$SHELL" != "/usr/bin/zsh" ]; then
    echo "📝 Setting zsh as default shell..."
    chsh -s $(which zsh)
    echo "✅ zsh set as default shell (restart terminal to apply)"
fi

echo ""
echo "🎉 Installation Complete!"
echo "========================"
echo ""
echo "Next steps:"
echo "1. Restart your terminal (or run: source ~/.zshrc)"
echo "2. Run: ./setup_mcp.sh"
echo ""

