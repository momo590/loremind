"""Loremind CLI — loremind watch / process / query / serve / mcp."""
from __future__ import annotations
import os
import sys
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from loremind.engine.tinm_adapter import CampaignStore
from loremind.processor import SessionProcessor
from loremind.schema import SessionDump, EntityType
from loremind.watcher import NotesWatcher, ICloudScanWatcher
from loremind.whatsapp.vision import extract_text_from_image

console = Console()


def _store(campaign: str) -> CampaignStore:
    return CampaignStore(campaign)


@click.group()
@click.option("--campaign", "-c", default="default", envvar="LOREMIND_CAMPAIGN",
              help="Campaign name (default: 'default')")
@click.pass_context
def main(ctx: click.Context, campaign: str) -> None:
    """Loremind — your AI remembers every story you tell."""
    ctx.ensure_object(dict)
    ctx.obj["campaign"] = campaign


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--auto-process", is_flag=True, default=False,
              help="Automatically process notes after each change.")
@click.pass_context
def watch(ctx: click.Context, path: str, auto_process: bool) -> None:
    """Watch a file or folder for session note changes."""
    campaign = ctx.obj["campaign"]
    store = _store(campaign)
    processor = SessionProcessor(store)
    watch_path = Path(path)

    console.print(f"[green]Watching[/green] {watch_path} for campaign [bold]{campaign}[/bold]")
    console.print("Press Ctrl+C to stop.\n")

    def on_change(changed_path: Path) -> None:
        console.print(f"  [dim]{changed_path.name}[/dim] changed")
        if auto_process:
            text = changed_path.read_text(encoding="utf-8", errors="replace")
            dump = SessionDump(
                session_number=len(list((store.root / "raw").glob("session-*.md"))) + 1,
                raw_text=text,
                source="file",
            )
            entities = processor.process(dump)
            for e in entities:
                console.print(f"  [cyan]+[/cyan] {e.entity_type.value}: {e.name}")

    watcher = NotesWatcher(callback=on_change)
    watcher.add(watch_path)
    watcher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
        console.print("\nStopped.")


@main.command()
@click.argument("text", required=False)
@click.option("--file", "-f", type=click.Path(exists=True), help="Read notes from file.")
@click.option("--session", "-s", type=int, default=None, help="Session number (auto-detected if omitted).")
@click.pass_context
def process(ctx: click.Context, text: Optional[str], file: Optional[str], session: Optional[int]) -> None:
    """Process session notes into NPCs, locations, factions, and threads."""
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

    session_num = session or len(list((store.root / "raw").glob("session-*.md"))) + 1

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

    # Simple keyword match first
    query_lower = query.lower()
    matches = [e for e in entities if query_lower in e.name.lower() or query_lower in e.summary.lower()]

    if not matches:
        console.print(f"[yellow]No entities found matching '{query}'.[/yellow]")
        return

    for e in matches:
        console.print(f"\n[bold cyan]{e.entity_type.value.upper()}[/bold cyan] — [bold]{e.name}[/bold]")
        console.print(e.summary)
        if e.details:
            for k, v in e.details.items():
                console.print(f"  [dim]{k}:[/dim] {v}")


@main.command()
@click.argument("image_path", type=click.Path(exists=True))
@click.pass_context
def scan(ctx: click.Context, image_path: str) -> None:
    """Extract text from a handwritten notes image and process it."""
    campaign = ctx.obj["campaign"]
    store = _store(campaign)
    processor = SessionProcessor(store)

    console.print(f"Reading {image_path}...")
    text = extract_text_from_image(Path(image_path))

    if not text:
        console.print("[red]Could not extract text from image.[/red]")
        sys.exit(1)

    console.print("[dim]Extracted text:[/dim]")
    console.print(text)
    console.print()

    session_num = len(list((store.root / "raw").glob("session-*.md"))) + 1
    dump = SessionDump(session_number=session_num, raw_text=text, source="scan", image_paths=[image_path])
    entities = processor.process(dump)

    for e in entities:
        console.print(f"[green]+[/green] {e.entity_type.value}: [bold]{e.name}[/bold]")


@main.command()
@click.option("--port", default=5001, help="Port for WhatsApp webhook server.")
@click.option("--provider", default="twilio", type=click.Choice(["twilio", "meta"]))
@click.pass_context
def serve(ctx: click.Context, port: int, provider: str) -> None:
    """Start the WhatsApp webhook server."""
    os.environ.setdefault("WHATSAPP_PROVIDER", provider)
    os.environ.setdefault("LOREMIND_CAMPAIGN", ctx.obj["campaign"])

    from loremind.whatsapp.bot import app as flask_app
    console.print(f"[green]WhatsApp webhook[/green] running on port {port} (provider: {provider})")
    flask_app.run(host="0.0.0.0", port=port)


@main.command()
@click.pass_context
def mcp(ctx: click.Context) -> None:
    """Start the MCP server (inject campaign memory into Claude Desktop)."""
    # MCP server implementation — serves campaign context as MCP resources
    campaign = ctx.obj["campaign"]
    store = _store(campaign)
    context = store.context_block()
    # Minimal stdout MCP — reads JSON-RPC from stdin, responds on stdout
    import json
    for line in sys.stdin:
        try:
            req = json.loads(line)
            method = req.get("method", "")
            if method == "resources/list":
                print(json.dumps({"result": {"resources": [{"uri": "loremind://campaign", "name": campaign}]}}))
            elif method == "resources/read":
                print(json.dumps({"result": {"contents": [{"text": context}]}}))
            else:
                print(json.dumps({"result": {}}))
            sys.stdout.flush()
        except Exception:
            continue
