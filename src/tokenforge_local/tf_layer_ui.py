from __future__ import annotations

from html import escape
import re
from typing import Any

from .app_state import coerce_int, mark_dirty, set_status, state
from .models import LayerBand
from .palette import enabled_colors
from .tf_layer_plan import (
    nudge_stop,
    preview_layer_plan,
    reset_layer_color_stops,
    set_band_span_layers,
    set_stop_color,
    set_stop_start_layer,
    sync_layer_color_stops,
)

try:
    from nicegui import ui
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("NiceGUI is not installed. Run `pip install -e .` or `pip install -r requirements.txt` first.") from exc


_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _safe_hex(value: str) -> str:
    value = str(value or "").strip()
    return value if _HEX_RE.fullmatch(value) else "#888888"


def _after_layer_edit(message: str | None = None) -> None:
    mark_dirty()
    refresh_layer_controls()
    try:
        from .tf_preview_helpers import refresh_reduced_color_preview

        refresh_reduced_color_preview(False)
    except Exception:
        pass
    if message:
        set_status(message, notify=False)


def reset_layer_controls() -> None:
    reset_layer_color_stops(state.project)
    _after_layer_edit("Layer color plan reset to an even dark-to-light order.")


def _change_stop_color(index: int, raw_name: Any) -> None:
    set_stop_color(state.project, index, str(raw_name or ""))
    _after_layer_edit("Layer color order updated.")


def _change_stop_start(index: int, raw_value: Any) -> None:
    stops = sync_layer_color_stops(state.project)
    fallback = stops[index].start_layer if 0 <= index < len(stops) else 1
    set_stop_start_layer(state.project, index, coerce_int(raw_value, fallback, minimum=1))
    _after_layer_edit("Layer shift point updated.")


def _nudge_stop(index: int, delta: int) -> None:
    nudge_stop(state.project, index, delta)
    _after_layer_edit("Layer shift point moved.")


def _change_band_span(index: int, raw_value: Any) -> None:
    set_band_span_layers(state.project, index, coerce_int(raw_value, 1, minimum=1))
    _after_layer_edit("Layer span updated.")


def _node_percent(layer_number: int, total_layers: int) -> float:
    if total_layers <= 1:
        return 0.0
    return ((layer_number - 1) / (total_layers - 1)) * 100.0


def _render_vertical_slider(bands: list[LayerBand], total_layers: int) -> None:
    height_px = max(260, min(460, total_layers * 30))
    segment_html: list[str] = []
    node_html: list[str] = []
    for band in bands:
        start = band.layer_number
        end = band.end_layer or band.layer_number
        bottom_percent = ((start - 1) / total_layers) * 100.0
        height_percent = max(4.0, ((end - start + 1) / total_layers) * 100.0)
        color_hex = _safe_hex(band.color_hex)
        label = escape(f"L{start}" if start == end else f"L{start}-{end}")
        name = escape(band.color_name)
        segment_html.append(
            f'<div title="{name} {label}" style="position:absolute; left:28px; bottom:{bottom_percent:.2f}%; '
            f'width:22px; height:{height_percent:.2f}%; background:{color_hex}; border-radius:12px; '
            f'border:1px solid rgba(0,0,0,.35);"></div>'
        )
        node_bottom = _node_percent(start, total_layers)
        node_html.append(
            f'<div title="{name} starts at layer {start}" style="position:absolute; left:21px; bottom:calc({node_bottom:.2f}% - 12px); '
            f'width:36px; height:36px; border-radius:50%; background:{color_hex}; border:3px solid white; '
            f'box-shadow:0 1px 5px rgba(0,0,0,.35); display:flex; align-items:center; justify-content:center; '
            f'font-size:10px; font-weight:700; color:#111;">{start}</div>'
        )

    ui.html(
        f"""
        <div style="display:flex; gap:14px; align-items:stretch;">
          <div style="width:84px; height:{height_px}px; position:relative; border-radius:22px; padding:10px 0;
                      background:linear-gradient(180deg,#f7f7f7,#e9e9e9); border:1px solid #d0d0d0;">
            <div style="position:absolute; left:38px; top:16px; bottom:16px; width:4px; background:#202020; border-radius:4px; opacity:.55;"></div>
            {''.join(segment_html)}
            {''.join(node_html)}
          </div>
          <div style="font-size:12px; line-height:1.45; color:#444; max-width:280px;">
            <b>Manual color-change rail</b><br>
            Bottom is layer 1. Circular nodes are shift points. Band height shows how many slicer layers each color spans.
            Use the compact editor below for exact layer numbers and color swaps.
          </div>
        </div>
        """
    )


def _band_summary(band: LayerBand) -> str:
    end = band.end_layer or band.layer_number
    return f"{band.color_name}: L{band.layer_number}-{end} · {band.span_layers} layer{'s' if band.span_layers != 1 else ''}"


def _render_band_controls(bands: list[LayerBand], total_layers: int) -> None:
    options = [color.name for color in enabled_colors(state.project.enabled_palette_colors)]
    with ui.expansion("Edit color shift points and spans", value=True).classes("w-full"):
        ui.label("Change the color order, move the start layer for each node, or set a span to push the next node.").classes("text-xs text-gray-600")
        for index, band in enumerate(bands):
            with ui.row().classes("items-center no-wrap gap-2 w-full"):
                ui.label(_band_summary(band)).classes("min-w-48 text-sm font-bold")
                ui.select(options, label="Color", value=band.color_name, on_change=lambda e, i=index: _change_stop_color(i, e.value)).classes("w-36")
                start_input = ui.number(
                    "Start",
                    value=band.layer_number,
                    min=1,
                    max=total_layers,
                    step=1,
                    on_change=lambda e, i=index: _change_stop_start(i, e.value),
                ).classes("w-24")
                if index == 0:
                    start_input.props("disable")
                span_input = ui.number(
                    "Span",
                    value=band.span_layers,
                    min=1,
                    max=total_layers,
                    step=1,
                    on_change=lambda e, i=index: _change_band_span(i, e.value),
                ).classes("w-24")
                if index == len(bands) - 1:
                    span_input.props("disable")
                ui.button("↑", on_click=lambda i=index: _nudge_stop(i, 1)).props("dense").tooltip("Move this shift point later/higher")
                ui.button("↓", on_click=lambda i=index: _nudge_stop(i, -1)).props("dense").tooltip("Move this shift point earlier/lower")
            ui.label(f"G-code checkpoint: {band.action}").classes("text-xs text-gray-700")


def refresh_layer_controls() -> None:
    container = state.layer_editor_container
    if container is None:
        return
    container.clear()
    with container:
        with ui.card().classes("w-full gap-2"):
            ui.label("Layer color plan and G-code change points").classes("font-bold")
            ui.label("This controls the actual color-to-Z mapping used for preview, STL height bands, swap CSV, and print notes.").classes("text-sm text-gray-600")
            if len(enabled_colors(state.project.enabled_palette_colors)) < 2:
                ui.label("Enable at least two filament colors to edit the layer color plan.").classes("text-sm text-orange-700")
                return

            try:
                plan, _colors = preview_layer_plan(state.project)
            except Exception as exc:
                ui.label(f"Layer plan unavailable: {exc}").classes("text-sm text-red-700")
                return

            if plan.snap_warning:
                ui.label(plan.snap_warning).classes("text-sm text-orange-700")

            ui.label(f"Physical layer count: {plan.total_layers} · finished thickness: {plan.finished_thickness_mm:.3f} mm").classes("text-sm")
            with ui.row().classes("items-start gap-4 w-full"):
                _render_vertical_slider(plan.color_layers, plan.total_layers)
                with ui.column().classes("gap-2 grow"):
                    _render_band_controls(plan.color_layers, plan.total_layers)
                    with ui.row().classes("gap-2"):
                        ui.button("Reset layer plan", on_click=reset_layer_controls).props("dense")
                        ui.button("Refresh layer plan", on_click=refresh_layer_controls).props("dense")
