# Loremind

**Your AI remembers every story you tell.**

Loremind gives your AI the full memory of your campaign — NPCs, locations, factions, unresolved threads — across every session. Works with Claude, ChatGPT, and any AI tool that supports MCP.

No subscription. No cloud. Your campaign lives in files you own.

---

## What it does

You run a session. You take notes — typed, handwritten, or sent via WhatsApp. Loremind watches what you write and quietly builds your campaign wiki for you.

Three months later, when a player asks "wait, what was the deal with Brask the Lopsided?", your AI knows. You don't have to remember where you wrote it down.

---

## How to use it

### Option A — Type your notes (any editor)

```bash
# Point Loremind at your session notes file
loremind watch ~/Documents/session-notes.md

# After session: structure into NPCs, locations, threads
loremind process
```

Works with Obsidian, BBEdit, TextEdit, VS Code, Notepad — any editor that saves to disk.

### Option B — WhatsApp (photos + chat)

Add the Loremind WhatsApp number to your contacts.

During or after session:
- **Send a photo** of your handwritten notes → Loremind reads it and stores it
- **Ask a question** → "Who is the third leader of the Iron Circle?" → Loremind answers from your campaign memory

No app install. No setup. Just WhatsApp.

### Option C — iCloud Drive scan

Use iPhone's built-in document scanner (Files app → long press → Scan Documents). Save to `iCloud Drive/Loremind/scans/`. Loremind picks it up automatically.

---

## Install

```bash
curl -fsSL https://loremind.app/install.sh | bash
```

Requires Python 3.11+ and an Anthropic or OpenAI API key.

---

## What gets stored

Your campaign data lives in `~/.loremind/campaigns/` as plain markdown files. No database. No cloud. Fully readable without any tool.

```
~/.loremind/campaigns/my-campaign/
├── npcs/
│   ├── brask-the-lopsided.md
│   └── patel-the-merchant.md
├── locations/
│   └── the-iron-circle-headquarters.md
├── factions/
│   └── iron-circle.md
└── threads/
    └── unresolved-dragon-cult-loyalty.md
```

---

## AI client integration (MCP)

Add Loremind to your AI client so it has your campaign memory in every conversation:

```json
{
  "mcpServers": {
    "loremind": {
      "command": "loremind",
      "args": ["mcp"]
    }
  }
}
```

Works with Claude Desktop, any MCP-compatible client.

---

## Differentiators

- **Client-agnostic** — works with whatever AI you already use
- **Local-first** — your data never leaves your machine
- **Open source** — MIT license, no lock-in
- **WhatsApp-native** — no app to install, photos just work

---

## Roadmap

- **v0.1** — File watcher + WhatsApp bot + iCloud scan
- **v0.2** — Passive screen capture (any app, fork of [Clicky](https://github.com/farzaa/clicky))
- **v0.3** — Cross-device sync via PCP protocol

---

## License

MIT — do whatever you want with it.
