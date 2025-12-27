# Knap

An AI agent that lets you interact with your Obsidian vault through Telegram or the command line.

## Features

- **Natural Language** - Talk to your vault like you would to an assistant
- **Full CRUD** - Create, read, update, and delete notes
- **Surgical Edits** - Find and replace text without rewriting entire notes
- **Search** - Full-text search and tag-based search
- **Navigation** - List folders, find backlinks
- **Daily Notes** - Get or create today's daily note
- **Frontmatter** - Read and update YAML metadata
- **Voice Messages** - Send voice notes, transcribed via Whisper
- **Vault Indexing** - Agent knows your vault structure without searching
- **Custom Guidelines** - Define agent behavior with a `KNAP.md` note
- **Persistent History** - Conversations persist across restarts
- **User Authentication** - Whitelist-based access control
- **Action Confirmations** - Confirm destructive actions before execution
- **Configurable Settings** - Adjust behavior conversationally

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Telegram account
- OpenAI API key

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 2. Get Your Telegram User ID

1. Message [@userinfobot](https://t.me/userinfobot)
2. Copy your user ID

### 3. Get an OpenAI API Key

1. Go to [platform.openai.com](https://platform.openai.com)
2. Create an API key

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key
VAULT_PATH=/path/to/your/obsidian/vault
ALLOWED_USER_IDS=your_telegram_user_id
```

You can add multiple users separated by commas:

```bash
ALLOWED_USER_IDS=123456789,987654321
```

### 5. Install and Run

```bash
# Install dependencies
make install

# Run the bot
make run
```

Or without make:

```bash
uv sync
uv run python -m knap
```

You should see:

```
Vault: /path/to/your/vault
Users: [123456789]
Knap started ✓
Connected as @YourBotName
```

## Usage

Knap can be used via Telegram bot or CLI. Both interfaces understand natural language and infer your intent.

### Telegram Bot

Send messages to your bot on Telegram.

### Examples

| You say | Knap does |
|---------|------------|
| "I bought potatoes" | Finds shopping list, checks off potatoes |
| "Create a shopping list with eggs and milk" | Creates note with checklist items |
| "What notes do I have about Python?" | Searches and summarizes results |
| "Show me my daily note" | Gets or creates today's daily note |
| "Add a task: Review PR #123" | Appends task to appropriate note |
| "What links to my Ideas note?" | Finds all backlinks |

### Voice Messages

Send a voice message and Knap will transcribe it using OpenAI Whisper, then process it as text.

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Show help message |
| `/clear` | Clear conversation history |

### CLI

The CLI provides a terminal-based interface to interact with your vault.

```bash
# Interactive mode (REPL)
knap-cli

# Single message (non-interactive)
knap-cli -m "What notes do I have about Python?"

# Utility commands
knap-cli --refresh-index
knap-cli --clear-history
```

**Interactive mode commands:**

| Command | Description |
|---------|-------------|
| `/clear` | Clear conversation history |
| `/refresh` | Refresh vault index |
| `/help` | Show help |
| `exit` | Exit the CLI |
| `approve` | Approve a pending plan |
| `reject` | Reject a pending plan |

**CLI flags:**

| Flag | Description |
|------|-------------|
| `-m`, `--message` | Send a single message and exit |
| `--clear-history` | Clear conversation history and exit |
| `--refresh-index` | Refresh the vault index and exit |

The CLI uses a separate conversation history from Telegram users. Write operations that would require confirmation in Telegram are auto-confirmed in CLI mode (you can see the actions in the logs).

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from BotFather | required (bot only) |
| `OPENAI_API_KEY` | OpenAI API key | required |
| `VAULT_PATH` | Absolute path to Obsidian vault | required |
| `ALLOWED_USER_IDS` | Comma-separated Telegram user IDs | required (bot only) |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4o` |

For CLI-only usage, you only need `OPENAI_API_KEY` and `VAULT_PATH`.

## Customization

### KNAP.md

Create a `KNAP.md` note in your vault root to customize the agent's behavior. This note is read on every message and injected into the system prompt.

Example `KNAP.md`:

```markdown
## Language
- Always respond in Brazilian Portuguese

## Note Organization
- New notes go in the "Inbox" folder
- Add #status/new tag to new notes
- Use wikilinks to connect related notes

## Daily Notes
- Located in "Journal/Daily"
- Format: YYYY-MM-DD

## Shopping List
- My shopping list is at "Lists/Compras.md"
- Items use checkbox format: - [ ] Item
```

### Action Confirmations

All write operations (create, update, edit, delete) require confirmation before executing. When Knap wants to modify a note, it shows a preview with before/after and inline buttons:

```
📄 Replace Lista de Compras.md
┌─────────────────────────┐
│ - [x] Batata            │
│ - [ ] Trigo             │
└─────────────────────────┘
↓
┌─────────────────────────┐
│ - [x] Batata            │
│ - [x] Trigo             │
└─────────────────────────┘

[✓ Confirm] [✗ Cancel]
```

When multiple actions are pending, a "Confirm All" button appears.

To disable confirmations, just tell Knap: "Disable confirmations" or "Turn off confirmations".

### Settings

Knap settings are stored in `.knap/settings.json` and can be changed conversationally:

| Setting | Description | Default |
|---------|-------------|---------|
| `require_confirmations` | Require confirmation for write operations | `true` |
| `confirmation_timeout_minutes` | How long confirmations stay valid | `5` |

Examples:
- "Disable confirmations"
- "Enable confirmations"
- "Show my settings"

### Vault Index

Knap automatically indexes your vault and stores data at `.knap/` inside your vault:

```
.knap/
├── index.json              # Vault structure, tags, note summaries
├── settings.json           # User settings
├── pending_confirmations.json  # Pending action confirmations
└── conversations/
    └── {user_id}.json      # Conversation history per user
```

This gives the agent a "mental map" of your vault - it knows your folder structure, tags, and recent notes without needing to search every time.

The index auto-refreshes when files change. You can also ask the agent to "refresh your understanding of my vault".

## Available Tools

The agent has access to these tools:

| Tool | Description |
|------|-------------|
| `read_note` | Read contents of a note |
| `create_note` | Create a new note |
| `update_note` | Replace entire note content |
| `edit_note` | Find and replace text (surgical edits) |
| `append_to_note` | Add content to end of note |
| `delete_note` | Delete a note |
| `search_content` | Full-text search across vault |
| `search_by_tag` | Find notes by tag |
| `list_folder` | List folder contents |
| `get_backlinks` | Find notes linking to a note |
| `get_daily_note` | Get or create today's daily note |
| `get_frontmatter` | Read note YAML metadata |
| `set_frontmatter` | Update note metadata |
| `refresh_vault_index` | Rebuild vault index |
| `get_settings` | View current Knap settings |
| `update_settings` | Change Knap settings |

## Development

### Setup

```bash
# Install with dev dependencies
make install-dev
```

### Commands

```bash
make run          # Run the Telegram bot
make cli          # Run the CLI (interactive)
make test         # Run tests
make test-v       # Run tests (verbose)
make lint         # Check for lint errors
make lint-fix     # Auto-fix lint issues
make format       # Format code with ruff
make clean        # Clean cache files
```

### Project Structure

```
knap/
├── knap/
│   ├── agent/          # AI agent core
│   │   ├── core.py     # Main agent loop
│   │   └── prompts.py  # System prompts
│   ├── indexer/        # Vault indexing
│   │   ├── scanner.py  # Scans vault, builds index
│   │   └── summary.py  # Generates text summary
│   ├── storage/        # Persistence
│   │   ├── history.py  # Conversation history
│   │   ├── settings.py # User settings & confirmations
│   │   └── vault_index.py
│   ├── telegram/       # Telegram bot
│   │   └── bot.py
│   ├── tools/          # Vault tools
│   │   ├── base.py     # Tool base class
│   │   ├── read.py     # Read, search tools
│   │   ├── write.py    # Create, update, delete
│   │   ├── edit.py     # Surgical edits
│   │   ├── settings.py # Settings tools
│   │   └── ...
│   ├── config.py       # Settings
│   ├── main.py         # Telegram bot entry point
│   └── cli.py          # CLI entry point
├── tests/              # Test suite
├── Makefile
└── pyproject.toml
```
