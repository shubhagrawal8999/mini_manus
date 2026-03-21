# mini_manus
# Mini-Manus AI Agent

24/7 autonomous AI agent on Telegram. DeepSeek primary, OpenAI fallback.

## Quick Start

### 1. Local Development

```bash
# Clone and setup
git clone &lt;your-repo&gt;
cd mini-manus
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
python -m bot.main
