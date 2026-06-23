from __future__ import annotations

"""NiceGUI presentation helpers for a portfolio-to-Tokenforge handoff."""

from collections.abc import Callable
from typing import Any

from .handoff import TokenforgeHandoff, is_safe_external_url

try:
    from nicegui import ui
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("NiceGUI is not installed. Run `pip install -e .` or `pip install -r requirements.txt` first.") from exc


def _url_field(label: str, value: str) -> None:
    ui.input(label, value=value).props("readonly dense").classes("w-full")


def build_handoff_intake(
    handoff: TokenforgeHandoff | None,
    error: str | None,
    *,
    notes: str,
    request_json: str,
    on_notes_change: Callable[[str], None],
    on_prepare_request: Callable[[], None],
    on_download_request: Callable[[], None],
    on_use_image: Callable[[], None],
    on_use_model: Callable[[], None],
) -> Any | None:
    """Render a non-blocking handoff card or an invalid-link warning."""
    if error:
        with ui.card().classes("w-full border border-orange-300 bg-orange-50 gap-2"):
            ui.label("Gallery handoff not loaded").classes("text-lg font-bold text-orange-900")
            ui.label(f"Tokenforge is still ready to use normally. {error}").classes("text-sm text-orange-900")
        return None
    if handoff is None:
        return None

    item = handoff.item
    print_info = handoff.print
    with ui.card().classes("w-full border border-primary bg-blue-50 gap-3"):
        ui.label("Portfolio gallery handoff").classes("text-lg font-bold")
        ui.label(item.name or "Selected gallery item").classes("text-xl font-bold")
        if item.description:
            ui.label(item.description).classes("text-sm text-gray-700")
        ui.label(f"Source: {handoff.source or 'portfolio gallery'} | Intent: {handoff.intent or 'request print'}").classes("text-sm text-gray-700")

        if item.gallery_url:
            _url_field("Source gallery URL", item.gallery_url)
            if is_safe_external_url(item.gallery_url):
                ui.link("Open gallery source", item.gallery_url, new_tab=True).classes("text-sm")

        with ui.grid(columns=2).classes("w-full gap-3"):
            with ui.column().classes("gap-1"):
                ui.label("Gallery image").classes("font-bold")
                if item.image_url:
                    _url_field("Image URL", item.image_url)
                    ui.button("Use gallery image as source", on_click=on_use_image).props("dense color=primary")
                else:
                    ui.label("No gallery image URL was included.").classes("text-sm text-gray-600")
            with ui.column().classes("gap-1"):
                ui.label("Gallery model").classes("font-bold")
                if item.model_url:
                    _url_field("Model URL", item.model_url)
                    ui.button("Use gallery model in 3D mode", on_click=on_use_model).props("dense color=primary")
                else:
                    ui.label("No gallery model URL was included.").classes("text-sm text-gray-600")

        print_bits = [bit for bit in [print_info.category, print_info.material] if bit]
        if print_info.nozzle_mm is not None:
            print_bits.append(f"{print_info.nozzle_mm:g} mm nozzle")
        if print_info.layer_height_mm is not None:
            print_bits.append(f"{print_info.layer_height_mm:g} mm layers")
        if print_info.colors:
            print_bits.append("colors: " + ", ".join(print_info.colors))
        if print_info.estimated_grams is not None:
            print_bits.append(f"~{print_info.estimated_grams:g} g")
        if print_info.estimated_time_minutes is not None:
            print_bits.append(f"~{print_info.estimated_time_minutes:g} min")
        ui.label("Print details: " + (" | ".join(print_bits) or "No print details supplied.")).classes("text-sm")
        ui.label("Print notes: " + (print_info.notes or "No notes supplied.")).classes("text-sm text-gray-700")

        ui.textarea("Notes for Printdesk", value=notes, on_change=lambda e: on_notes_change(str(e.value or ""))).classes("w-full")
        with ui.row().classes("items-center gap-2 flex-wrap"):
            ui.button("Prepare print request", on_click=on_prepare_request).props("color=primary")
            ui.button("Download print request JSON", on_click=on_download_request).props("dense")
        return ui.textarea("Prepared Printdesk request JSON", value=request_json).props("readonly").classes("w-full")
