"""
app.py – Interactive CLI quoting interface
Uses Rich for pretty terminal output.

Run:
    python app.py
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich import box

# Adjust path to import from src/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quote_engine import QuoteEngine

console = Console()

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "pricing_data.json")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")


# ──────────────────────────────────────────────────────────────────────────────
# Display helpers
# ──────────────────────────────────────────────────────────────────────────────

def print_banner() -> None:
    console.print()
    console.print(Panel.fit(
        "[bold white]JELD-WEN Interior Door Master Quoting Tool[/bold white]\n"
        "[dim]Powered by real PDF pricing data[/dim]",
        border_style="blue",
        padding=(1, 4),
    ))
    console.print()


def choose_from_list(prompt_text: str, options: List[str], allow_back: bool = False) -> Optional[str]:
    """Display a numbered list and return the chosen option string."""
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    table.add_column("Num", style="bold cyan", width=4)
    table.add_column("Option", style="white")

    for i, opt in enumerate(options, start=1):
        table.add_row(str(i), opt)
    if allow_back:
        table.add_row("0", "[dim]← Back[/dim]")

    console.print(table)

    while True:
        raw = Prompt.ask(f"[bold green]{prompt_text}[/bold green]")
        if allow_back and raw.strip() == "0":
            return None
        try:
            idx = int(raw.strip())
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            pass
        console.print("[red]  Invalid choice. Please enter a number from the list.[/red]")


def choose_multiple_from_list(prompt_text: str, options: List[str]) -> List[str]:
    """Let the user pick zero or more items from a list."""
    if not options:
        console.print("  [dim]No add-ons available for this dealer group.[/dim]")
        return []

    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    table.add_column("Num", style="bold cyan", width=4)
    table.add_column("Add-on", style="white")
    table.add_column("Price", style="yellow")

    # options is a list of dicts here
    option_names = []
    for i, addon in enumerate(options, start=1):
        name = addon.get("addon_name", "")
        price = addon.get("price", "")
        table.add_row(str(i), name, price)
        option_names.append(name)

    table.add_row("0", "[dim]Done – no more add-ons[/dim]", "")
    console.print(table)

    selected: List[str] = []
    while True:
        raw = Prompt.ask(
            f"[bold green]{prompt_text}[/bold green] "
            "[dim](enter number to toggle, 0 when done)[/dim]"
        )
        if raw.strip() == "0":
            break
        try:
            idx = int(raw.strip())
            if 1 <= idx <= len(option_names):
                name = option_names[idx - 1]
                if name in selected:
                    selected.remove(name)
                    console.print(f"  [yellow]Removed: {name}[/yellow]")
                else:
                    selected.append(name)
                    console.print(f"  [green]Added:   {name}[/green]")
            else:
                console.print("[red]  Invalid number.[/red]")
        except ValueError:
            console.print("[red]  Please enter a number.[/red]")

    return selected


def display_quote(quote: Dict[str, Any]) -> None:
    """Pretty-print the quote to the terminal."""
    console.print()
    console.print(Panel(
        f"[bold]Dealer Group:[/bold] {quote['dealer_group']}\n"
        f"[bold]Product:[/bold]      {quote['product_type'].title()} – {quote['style']}\n"
        f"[bold]Size:[/bold]         {quote['size']}   [bold]Variant:[/bold] {quote['variant']}\n"
        f"[bold]Quantity:[/bold]     {quote['quantity']}",
        title="[bold blue]Quote Summary[/bold blue]",
        border_style="blue",
    ))

    table = Table(show_header=True, header_style="bold white on dark_blue", box=box.ROUNDED)
    table.add_column("Description", style="white", min_width=40)
    table.add_column("Unit Price", style="yellow", justify="right")
    table.add_column("Qty", style="cyan", justify="right")
    table.add_column("Subtotal", style="green", justify="right")

    for item in quote["line_items"]:
        table.add_row(
            item["description"],
            f"${item['unit_price']:.2f}",
            str(item["quantity"]),
            f"${item['subtotal']:.2f}",
        )

    console.print(table)
    console.print(f"\n  [bold green]TOTAL: ${quote['total']:.2f}[/bold green]\n")

    if quote.get("errors"):
        console.print("[bold red]  Warnings:[/bold red]")
        for e in quote["errors"]:
            console.print(f"    [red]• {e}[/red]")
        console.print()


# ──────────────────────────────────────────────────────────────────────────────
# Main flow
# ──────────────────────────────────────────────────────────────────────────────

def run_quoting_session(engine: QuoteEngine) -> None:
    """Interactive quoting loop."""
    while True:
        console.rule("[bold blue]New Quote[/bold blue]")

        # 1. Dealer group
        groups = engine.get_dealer_groups()
        console.print("\n[bold]Step 1 – Select Dealer Group[/bold]")
        dealer = choose_from_list("Enter number", groups)
        if dealer is None:
            break

        # 2. Product type
        product_types = engine.get_product_types(dealer)
        if not product_types:
            console.print(f"[red]No products found for {dealer}[/red]")
            continue
        console.print("\n[bold]Step 2 – Select Product Type[/bold]")
        product_type = choose_from_list("Enter number", product_types, allow_back=True)
        if product_type is None:
            continue

        # 3. Style
        styles = engine.get_styles(dealer, product_type)
        if not styles:
            console.print(f"[red]No styles found for {dealer} / {product_type}[/red]")
            continue
        console.print("\n[bold]Step 3 – Select Door Style[/bold]")
        style = choose_from_list("Enter number", styles, allow_back=True)
        if style is None:
            continue

        # 4. Size
        sizes = engine.get_sizes(dealer, style, product_type)
        if not sizes:
            console.print(f"[red]No sizes found for {dealer} / {style}[/red]")
            continue
        # Separate base sizes from adders for cleaner display
        base_sizes = [s for s in sizes if "add" not in s.lower() and "height" not in s.lower()]
        adder_sizes = [s for s in sizes if s not in base_sizes]
        display_sizes = base_sizes + (["── Adders ──"] if adder_sizes else []) + adder_sizes
        display_sizes_clean = [s for s in display_sizes if s != "── Adders ──"]

        console.print("\n[bold]Step 4 – Select Size[/bold]")
        size = choose_from_list("Enter number", display_sizes_clean, allow_back=True)
        if size is None:
            continue

        # 5. Variant
        variants = engine.get_variants(dealer, style, size, product_type)
        if not variants:
            console.print(f"[red]No variants found for {style} / {size}[/red]")
            continue
        if len(variants) == 1:
            variant = variants[0]
            console.print(f"\n  [dim]Variant auto-selected: {variant}[/dim]")
        else:
            console.print("\n[bold]Step 5 – Select Variant[/bold]")
            variant = choose_from_list("Enter number", variants, allow_back=True)
            if variant is None:
                continue

        # 6. Quantity
        console.print("\n[bold]Step 6 – Quantity[/bold]")
        quantity = IntPrompt.ask("  Enter quantity", default=1)
        if quantity < 1:
            quantity = 1

        # 7. Add-ons
        available_addons = [
            a for a in engine.get_addons(dealer)
            if a.get("price_numeric") is not None
        ]
        selected_addons: List[str] = []
        if available_addons:
            console.print("\n[bold]Step 7 – Add-ons (optional)[/bold]")
            console.print("  [dim]Select any machining / jamb / hardware options:[/dim]\n")
            selected_addons = choose_multiple_from_list("Add/remove add-on", available_addons)

        # Build and display quote
        quote = engine.build_quote(
            dealer_group=dealer,
            product_type=product_type,
            style=style,
            size=size,
            variant=variant,
            selected_addons=selected_addons if selected_addons else None,
            quantity=quantity,
        )
        display_quote(quote)

        # Export option
        if Confirm.ask("  Export this quote to Excel?", default=True):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"quote_{dealer.replace(' ', '_')}_{style.replace(' ', '_')}_{timestamp}.xlsx"
            out_path = os.path.join(OUTPUT_DIR, filename)
            engine.export_quote_to_excel(quote, out_path)
            console.print(f"  [green]✓ Saved to: {out_path}[/green]")

        if not Confirm.ask("\n  Build another quote?", default=True):
            break

    console.print("\n[bold blue]Thank you for using the JELD-WEN Quoting Tool.[/bold blue]\n")


def main() -> None:
    print_banner()

    data_path = DATA_PATH
    if not os.path.isfile(data_path):
        console.print(
            f"[red]Pricing data not found at:[/red] {data_path}\n"
            "[yellow]Run the extraction pipeline first:[/yellow]\n"
            "  [bold]python run.py[/bold]\n"
        )
        sys.exit(1)

    console.print(f"[dim]Loading pricing data from {data_path}...[/dim]")
    engine = QuoteEngine(data_path)
    groups = engine.get_dealer_groups()
    total_records = sum(
        len(engine.get_styles(g, pt))
        for g in groups
        for pt in engine.get_product_types(g)
    )
    console.print(f"[green]✓ Loaded {len(groups)} dealer groups[/green]")
    console.print()

    run_quoting_session(engine)


if __name__ == "__main__":
    main()
