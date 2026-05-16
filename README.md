# Loremind

**Find your NPCs, promises, and forgotten threads months later — without having to remember where you wrote them down.**

---

Your sessions are chaotic. You invent unplanned storylines, NPCs, and locations on the fly. You forget to take notes, and when you do, they're rough.

Loremind takes your session recordings, messy notes, and anything else — and quietly builds your campaign wiki for you. New NPCs. New promises. Contradictions to address. Things you said you'd come back to and forgot.

You stay messy at the table. The structure happens afterward, when the chaos is done.

---

## How to feed it

You don't change how you take notes. Loremind meets you wherever you already work.

**Typing notes anywhere on your computer.** Point Loremind at your notes file (Obsidian vault, a markdown file, a text doc). It watches for changes and processes when you save.

```bash
loremind watch ~/Documents/session-notes.md
```

**Watching a window on your screen (Mac / Windows / Linux).** If you take notes in Apple Notes, Discord, or any app that doesn't save to a file, Loremind can watch a specific window — only the one you tell it to. Not your whole screen. A small menu bar / system tray app captures the focused window when you press a hotkey.

**Photos of handwritten notes via WhatsApp.** Add the Loremind number to your contacts. Take a photo of your session sheet, send it. That's it. Works at the table, on a phone, without an app install.

**Questions during or after the session.** Send a WhatsApp message: *"Who was the third leader of the Iron Circle?"* Loremind answers from your campaign memory.

---

## What you get

Your campaign data lives as plain markdown files on your machine. No database, no cloud, no subscription. Readable in any editor, backed up like any other folder.

```
~/.loremind/campaigns/iron-veil/
├── npcs/
│   ├── brask-the-lopsided.md
│   ├── patel-the-merchant.md
│   └── ...
├── locations/
├── factions/
└── threads/                    ← things you promised, never came back to
    ├── dragon-cult-loyalty-unresolved.md
    └── ...
```

---

## Install

```bash
curl -fsSL https://loremind.app/install.sh | bash
```

Requires Python 3.11+ and an API key from Anthropic or OpenAI.

---

## Use it with the AI you already use

Loremind can inject your campaign memory into Claude Desktop, Claude Code, ChatGPT (via MCP), or any tool that supports the open MCP protocol. Whatever you ask your AI assistant about — homebrew prep, NPC voices, plot inconsistencies — it has the full memory of your campaign.

```json
{
  "mcpServers": {
    "loremind": { "command": "loremind", "args": ["mcp"] }
  }
}
```

---

## What makes it different

- **Works with what you already have.** Notes app, Obsidian, Discord, paper — Loremind doesn't ask you to switch.
- **Your data stays yours.** Plain markdown files on your disk. No cloud account. Cancel anytime by deleting a folder.
- **Open source.** MIT license. Fork it, modify it, host it yourself.
- **Stays out of the way.** No AI doing your creative work. Loremind just remembers what you've already created.

---

## Roadmap

- **v0.1** — CLI processor, audio transcription (Whisper local), WhatsApp bot, cross-platform window capture (Tauri, Mac/Win/Linux)
- **v0.2** — review queue UI, MCP server (Claude Desktop integration), Discord bot
- **v0.3** — cross-device sync, custom entity types, Foundry VTT / Roll20 integration

---

## License

MIT — do whatever you want with it.
