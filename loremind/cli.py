"""Loremind CLI — loremind init / process / query / transcribe / serve / mcp.

v0.1 commands. Capture sources (Clicky, WhatsApp) post to the local HTTP
backend at 127.0.0.1:7788 — they are not invoked via this CLI.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from loremind.store import CampaignStore
from loremind.schema import SessionDump, EntityType

console = Console()


def _store(campaign: str) -> CampaignStore:
    return CampaignStore(campaign)


@click.group()
@click.option("--campaign", "-c", default="default", envvar="LOREMIND_CAMPAIGN",
              help="Campaign name (default: 'default')")
@click.option("--review", is_flag=True, default=False,
              help="Show extracted entities before writing (safer for trust-sensitive GMs)")
@click.pass_context
def main(ctx: click.Context, campaign: str, review: bool) -> None:
    """Loremind — your AI remembers every story you tell."""
    ctx.ensure_object(dict)
    ctx.obj["campaign"] = campaign
    ctx.obj["review"] = review


@main.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize Loremind — install Ollama if needed, pull models, create first campaign."""
    # T6 — implemented in loremind/installer.py
    console.print("[yellow]TODO[/yellow] T6 — installer.py")


@main.command()
@click.argument("text", required=False)
@click.option("--file", "-f", type=click.Path(exists=True), help="Read notes from file.")
@click.option("--session", "-s", type=int, default=None, help="Session number (auto-detected if omitted).")
@click.pass_context
def process(ctx: click.Context, text: Optional[str], file: Optional[str], session: Optional[int]) -> None:
    """Process session notes into NPCs, locations, factions, items, threads, lore."""
    from loremind.processor import SessionProcessor
    campaign = ctx.obj["campaign"]
    store = _store(campaign)
    processor = SessionProcessor(store)

    if file:
        raw_text = Path(file).read_text(encoding="utf-8", errors="replace")
        source = "file"
    elif text:
        raw_text = text
        source = "cli"
    else:
        console.print("[yellow]Reading from stdin...[/yellow]")
        raw_text = sys.stdin.read()
        source = "stdin"

    session_num = session or len(list((store.root / "sessions").glob("session-*.md"))) + 1
    dump = SessionDump(session_number=session_num, raw_text=raw_text, source=source)

    console.print(f"Processing session {session_num}...")
    entities = processor.process(dump)

    table = Table(title=f"Session {session_num} — Extracted Entities")
    table.add_column("Type", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Summary")

    for e in entities:
        table.add_row(e.entity_type.value, e.name, e.summary[:80])

    console.print(table)
    console.print(f"\n[green]Saved to[/green] {store.root}")


@main.command()
@click.argument("query")
@click.option("--type", "-t", "entity_type", type=click.Choice([t.value for t in EntityType]),
              default=None, help="Filter by entity type.")
@click.pass_context
def query(ctx: click.Context, query: str, entity_type: Optional[str]) -> None:
    """Query your campaign memory."""
    campaign = ctx.obj["campaign"]
    store = _store(campaign)

    et = EntityType(entity_type) if entity_type else None
    entities = store.all_entities(et)

    query_lower = query.lower()
    matches = [e for e in entities if query_lower in e.name.lower() or query_lower in e.summary.lower()]

    if not matches:
        console.print(f"[yellow]No entities found matching '{query}'.[/yellow]")
        return

    for e in matches:
        console.print(f"\n[bold cyan]{e.entity_type.value.upper()}[/bold cyan] — [bold]{e.name}[/bold]")
        console.print(e.summary)


@main.command()
@click.argument("audio_path", type=click.Path(exists=True))
@click.pass_context
def transcribe(ctx: click.Context, audio_path: str) -> None:
    """Transcribe a session recording (m4a, wav, mp3) via Whisper.cpp."""
    # T7 — implemented in loremind/audio.py
    console.print("[yellow]TODO[/yellow] T7 — audio.py (whisper.cpp wrapper)")


@main.command()
@click.option("--port", default=7788, help="HTTP backend port for Clicky + WhatsApp.")
@click.pass_context
def serve(ctx: click.Context, port: int) -> None:
    """Start the local HTTP backend for Clicky + WhatsApp bot integrations."""
    # T8 — implemented in loremind/server.py
    console.print(f"[yellow]TODO[/yellow] T8 — server.py (Flask on 127.0.0.1:{port})")
