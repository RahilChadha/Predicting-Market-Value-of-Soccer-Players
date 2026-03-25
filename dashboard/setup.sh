#!/bin/bash
# Job Dashboard Setup Script

set -e
echo "=== Job Dashboard Setup ==="

# Create .env from example if not exists
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env - please fill in your credentials"
fi

# Install Python dependencies
echo "Installing Python packages..."
pip install -r requirements.txt

# Install Playwright browser
echo "Installing Playwright Chromium browser..."
playwright install chromium

echo ""
echo "=== Setup Complete ==="
echo ""
echo "IMPORTANT: Before running, edit .env and set:"
echo "  WORKDAY_EMAIL=rahilchadha1@gmail.com"
echo "  WORKDAY_PASSWORD=your_password"
echo "  ANTHROPIC_API_KEY=your_api_key  (optional, for AI resume tailoring)"
echo ""
echo "To start the dashboard:"
echo "  python app.py"
echo ""
echo "Then open: http://localhost:8000"
