from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class StylePreset:
    key: str
    label: str
    group: str
    selectable: bool = True
    implemented: bool = True
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "group": self.group,
            "selectable": self.selectable,
            "implemented": self.implemented,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StylePreset":
        return cls(
            key=raw["key"],
            label=raw["label"],
            group=raw["group"],
            selectable=raw.get("selectable", True),
            implemented=raw.get("implemented", True),
            notes=raw.get("notes", ""),
        )


_STYLE_GROUPS: dict[str, list[StylePreset]] = {
    "Simple Frames": [
        StylePreset("thin_line", "Thin line", "Simple Frames"),
        StylePreset("double_line", "Double line", "Simple Frames"),
        StylePreset("corner_brackets", "Corner brackets", "Simple Frames", implemented=False, notes="Reserved for v0.2."),
        StylePreset("inset_panel", "Inset panel", "Simple Frames"),
        StylePreset("simple_plaque", "Simple plaque frame", "Simple Frames"),
    ],
    "Material Themes": [
        StylePreset("wood_frame", "Wood frame", "Material Themes"),
        StylePreset("smooth_metal", "Smooth metal plating", "Material Themes", implemented=False, notes="Reserved for v0.2."),
        StylePreset("riveted_metal", "Riveted metal frame", "Material Themes"),
        StylePreset("diamond_plate", "Diamond plate frame", "Material Themes"),
        StylePreset("stone_frame", "Stone frame", "Material Themes"),
        StylePreset("brick", "Brick", "Material Themes", implemented=False, notes="Reserved for v0.2."),
        StylePreset("marble_frame", "Marble frame", "Material Themes"),
        StylePreset("leather", "Leather", "Material Themes", implemented=False, notes="Reserved for v0.2."),
        StylePreset("parchment", "Parchment", "Material Themes", implemented=False, notes="Reserved for v0.2."),
        StylePreset("bone", "Bone", "Material Themes", implemented=False, notes="Reserved for v0.2."),
        StylePreset("crystal", "Crystal", "Material Themes", implemented=False, notes="Reserved for v0.2."),
        StylePreset("slate", "Slate", "Material Themes", implemented=False, notes="Reserved for v0.2."),
    ],
    "Fantasy / Decorative": [
        StylePreset("ornate_scrollwork", "Ornate scrollwork", "Fantasy / Decorative", implemented=False, notes="Reserved for v0.2."),
        StylePreset("vine_nature", "Vine / nature trim", "Fantasy / Decorative", implemented=False, notes="Reserved for v0.2."),
        StylePreset("rune_carved", "Rune-carved frame", "Fantasy / Decorative", implemented=False, notes="Reserved for v0.2."),
        StylePreset("gothic", "Gothic frame", "Fantasy / Decorative", implemented=False, notes="Reserved for v0.2."),
        StylePreset("mechanical_fantasy", "Mechanical fantasy frame", "Fantasy / Decorative", implemented=False, notes="Reserved for v0.2."),
    ],
    "Cultural / Regional Inspiration": [
        StylePreset("egyptian_hieroglyphic_panel", "Egyptian-inspired · Hieroglyphic panel frame", "Cultural / Regional Inspiration", implemented=False, notes="Future style. User-provided text required for real scripts."),
        StylePreset("egyptian_papyrus_gold", "Egyptian-inspired · Papyrus-and-gold frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("egyptian_desert_temple", "Egyptian-inspired · Desert temple frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("egyptian_scarab_corner", "Egyptian-inspired · Scarab corner ornament", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("japanese_torii_corner", "Japanese-inspired · Torii corner frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("japanese_wave_cloud", "Japanese-inspired · Wave-and-cloud frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("japanese_ink_brush", "Japanese-inspired · Ink-brush border", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("japanese_kanji_user_text", "Japanese-inspired · Kanji side text frame", "Cultural / Regional Inspiration", implemented=False, notes="User-provided text only; no fake script generation."),
        StylePreset("chinese_cloud_scroll", "Chinese-inspired · Cloud-scroll frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("chinese_jade_inlay", "Chinese-inspired · Jade-inlay frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("chinese_lattice", "Chinese-inspired · Lattice border", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("chinese_seal_stamp", "Chinese-inspired · Seal-stamp corner plate", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("korean_dancheong", "Korean-inspired · Dancheong pattern frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("korean_hanok_roofline", "Korean-inspired · Hanok roofline frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("korean_cloud_floral", "Korean-inspired · Cloud-and-floral border", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("celtic_knotwork", "Celtic-inspired · Knotwork frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("celtic_standing_stone", "Celtic-inspired · Standing-stone frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("celtic_woven_vine", "Celtic-inspired · Woven vine frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("norse_runestone", "Norse-inspired · Runestone frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("norse_knot_beast", "Norse-inspired · Knot-beast border", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("norse_frost_carved", "Norse-inspired · Frost-carved frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("mesoamerican_stepped_stone", "Mesoamerican-inspired · Stepped-stone frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("mesoamerican_sun_disc", "Mesoamerican-inspired · Sun-disc ornament frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("mesoamerican_temple_geo", "Mesoamerican-inspired · Geometric temple border", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("mediterranean_mosaic", "Mediterranean-inspired · Mosaic tile frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("mediterranean_laurel", "Mediterranean-inspired · Laurel frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("mediterranean_marble_column", "Mediterranean-inspired · Marble column frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("middle_eastern_geometric_tile", "Middle Eastern-inspired · Geometric tile frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("middle_eastern_archway", "Middle Eastern-inspired · Archway frame", "Cultural / Regional Inspiration", implemented=False),
        StylePreset("middle_eastern_filigree", "Middle Eastern-inspired · Filigree border", "Cultural / Regional Inspiration", implemented=False),
    ],
    "Genre / Setting Themes": [
        StylePreset("arcane_academy", "Arcane academy", "Genre / Setting Themes", implemented=False),
        StylePreset("alchemist_lab", "Alchemist lab", "Genre / Setting Themes", implemented=False),
        StylePreset("celestial_star_chart", "Celestial / star chart", "Genre / Setting Themes", implemented=False),
        StylePreset("infernal_demonic", "Infernal / demonic", "Genre / Setting Themes", implemented=False),
        StylePreset("necromancer_bone", "Necromancer bone frame", "Genre / Setting Themes", implemented=False),
        StylePreset("druidic_grove", "Druidic grove", "Genre / Setting Themes", implemented=False),
        StylePreset("clockwork_gearwork", "Clockwork / gearwork", "Genre / Setting Themes", implemented=False),
        StylePreset("steampunk_brass", "Steampunk brass", "Genre / Setting Themes", implemented=False),
        StylePreset("industrial_hazard", "Industrial hazard plate", "Genre / Setting Themes", implemented=False),
        StylePreset("sci_fi_circuit", "Sci-fi circuit frame", "Genre / Setting Themes", implemented=False),
        StylePreset("holographic_panel", "Holographic panel", "Genre / Setting Themes", implemented=False),
        StylePreset("cyberpunk_neon", "Cyberpunk neon panel", "Genre / Setting Themes", implemented=False),
        StylePreset("nautical_map", "Nautical map frame", "Genre / Setting Themes", implemented=False),
        StylePreset("pirate_treasure_map", "Pirate treasure map", "Genre / Setting Themes", implemented=False),
        StylePreset("ancient_ruin", "Ancient ruin", "Genre / Setting Themes", implemented=False),
        StylePreset("dungeon_stonework", "Dungeon stonework", "Genre / Setting Themes", implemented=False),
        StylePreset("royal_heraldic", "Royal heraldic frame", "Genre / Setting Themes", implemented=False),
        StylePreset("library_manuscript", "Library / manuscript frame", "Genre / Setting Themes", implemented=False),
        StylePreset("tavern_notice_board", "Tavern notice-board frame", "Genre / Setting Themes", implemented=False),
        StylePreset("monster_scale", "Monster-scale frame", "Genre / Setting Themes", implemented=False),
    ],
}


def all_style_presets() -> list[StylePreset]:
    presets: list[StylePreset] = []
    for group, group_presets in _STYLE_GROUPS.items():
        presets.append(StylePreset(f"__header__{group}", group, group, selectable=False, implemented=False))
        presets.extend(group_presets)
    return presets


def implemented_border_presets() -> list[StylePreset]:
    return [preset for preset in all_style_presets() if preset.selectable and preset.implemented]


def style_lookup() -> dict[str, StylePreset]:
    return {preset.key: preset for preset in all_style_presets() if preset.selectable}


def grouped_dropdown_options(include_future: bool = True) -> dict[str, str]:
    """Return key->label options while keeping headers visible in NiceGUI select controls."""
    options: dict[str, str] = {}
    for preset in all_style_presets():
        if not preset.selectable:
            options[preset.key] = f"── {preset.label} ──"
        elif include_future or preset.implemented:
            suffix = "" if preset.implemented else " (future)"
            options[preset.key] = f"{preset.label}{suffix}"
    return options


def fallback_if_unimplemented(style_key: str) -> str:
    preset = style_lookup().get(style_key)
    if preset and preset.implemented:
        return style_key
    return "thin_line"
