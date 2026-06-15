from __future__ import annotations

from .geometry import calculate_layer_plan
from typing import Any

from .models import FilamentColor, LayerColorStop, LayerPlan, ProjectState
from .palette import enabled_colors, sort_colors_for_layering


def _coerce_int(value: Any, fallback: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        result = int(fallback) if value is None or value == "" else int(float(value))
    except (TypeError, ValueError):
        result = int(fallback)
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _enabled_by_name(project: ProjectState) -> dict[str, FilamentColor]:
    return {color.name: color for color in enabled_colors(project.enabled_palette_colors)}


def _default_ordered_colors(project: ProjectState) -> list[FilamentColor]:
    return sort_colors_for_layering(enabled_colors(project.enabled_palette_colors))


def _default_starts(total_layers: int, color_count: int) -> list[int]:
    if color_count <= 0:
        return []
    base = total_layers // color_count
    remainder = total_layers % color_count
    starts: list[int] = []
    current = 1
    for index in range(color_count):
        starts.append(current)
        current += base + (1 if index < remainder else 0)
    return starts


def _safe_total_layers(project: ProjectState, color_count: int) -> int:
    try:
        dummy_colors = [FilamentColor(f"Layer {index + 1}", "#000000", True) for index in range(max(1, min(color_count, 1)))]
        return calculate_layer_plan(project.printer_preferences, dummy_colors).total_layers
    except Exception:
        return max(1, color_count)


def _normalize_starts(stops: list[LayerColorStop], total_layers: int) -> None:
    if not stops or len(stops) > total_layers:
        return
    stops.sort(key=lambda stop: (stop.start_layer, stop.color_name.lower()))
    for index, stop in enumerate(stops):
        minimum = 1 if index == 0 else stops[index - 1].start_layer + 1
        maximum = total_layers - (len(stops) - index) + 1
        stop.start_layer = _coerce_int(stop.start_layer, minimum, minimum=minimum, maximum=maximum)
    stops[0].start_layer = 1


def sync_layer_color_stops(project: ProjectState) -> list[LayerColorStop]:
    enabled_map = _enabled_by_name(project)
    ordered_defaults = _default_ordered_colors(project)
    total_layers = _safe_total_layers(project, len(ordered_defaults))
    default_starts = _default_starts(max(total_layers, len(ordered_defaults)), len(ordered_defaults))
    default_start_by_name = {color.name: default_starts[index] for index, color in enumerate(ordered_defaults)}

    stops: list[LayerColorStop] = []
    seen: set[str] = set()
    for stop in sorted(project.layer_color_stops, key=lambda item: item.start_layer):
        color = enabled_map.get(stop.color_name)
        if color is None or color.name in seen:
            continue
        stops.append(LayerColorStop(_coerce_int(stop.start_layer, default_start_by_name.get(color.name, 1), minimum=1), color.name, color.hex))
        seen.add(color.name)

    for color in ordered_defaults:
        if color.name not in seen:
            stops.append(LayerColorStop(default_start_by_name.get(color.name, 1), color.name, color.hex))
            seen.add(color.name)

    _normalize_starts(stops, total_layers)
    project.layer_color_stops = stops
    return stops


def layer_colors_for_project(project: ProjectState) -> list[FilamentColor]:
    enabled_map = _enabled_by_name(project)
    stops = sync_layer_color_stops(project)
    colors: list[FilamentColor] = []
    for stop in stops:
        color = enabled_map.get(stop.color_name)
        if color is not None:
            colors.append(FilamentColor(color.name, color.hex, True))
    return colors


def preview_layer_plan(project: ProjectState) -> tuple[LayerPlan, list[FilamentColor]]:
    colors = layer_colors_for_project(project)
    return calculate_layer_plan(project.printer_preferences, colors, custom_stops=project.layer_color_stops), colors


def reset_layer_color_stops(project: ProjectState) -> None:
    project.layer_color_stops = []
    sync_layer_color_stops(project)


def set_stop_color(project: ProjectState, index: int, color_name: str) -> None:
    stops = sync_layer_color_stops(project)
    if index < 0 or index >= len(stops):
        return
    enabled_map = _enabled_by_name(project)
    if color_name not in enabled_map:
        return

    existing_index = next((position for position, stop in enumerate(stops) if stop.color_name == color_name), None)
    if existing_index is not None and existing_index != index:
        stops[index].color_name, stops[existing_index].color_name = stops[existing_index].color_name, stops[index].color_name
        stops[index].color_hex = enabled_map[stops[index].color_name].hex
        stops[existing_index].color_hex = enabled_map[stops[existing_index].color_name].hex
    else:
        stops[index].color_name = color_name
        stops[index].color_hex = enabled_map[color_name].hex
    project.layer_color_stops = stops


def set_stop_start_layer(project: ProjectState, index: int, start_layer: int) -> None:
    stops = sync_layer_color_stops(project)
    if index <= 0 or index >= len(stops):
        return
    total_layers = _safe_total_layers(project, len(stops))
    minimum = stops[index - 1].start_layer + 1
    maximum = total_layers - (len(stops) - index) + 1
    stops[index].start_layer = _coerce_int(start_layer, stops[index].start_layer, minimum=minimum, maximum=maximum)
    _normalize_starts(stops, total_layers)
    project.layer_color_stops = stops


def nudge_stop(project: ProjectState, index: int, delta_layers: int) -> None:
    stops = sync_layer_color_stops(project)
    if index <= 0 or index >= len(stops):
        return
    set_stop_start_layer(project, index, stops[index].start_layer + delta_layers)


def set_band_span_layers(project: ProjectState, index: int, span_layers: int) -> None:
    stops = sync_layer_color_stops(project)
    if index < 0 or index >= len(stops) - 1:
        return
    total_layers = _safe_total_layers(project, len(stops))
    requested_span = _coerce_int(span_layers, stops[index + 1].start_layer - stops[index].start_layer, minimum=1)
    stops[index + 1].start_layer = stops[index].start_layer + requested_span
    _normalize_starts(stops, total_layers)
    project.layer_color_stops = stops
