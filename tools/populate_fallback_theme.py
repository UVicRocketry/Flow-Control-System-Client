#!/usr/bin/env python3
"""
Populate Breeze Fallback Icon Theme

Finds requested icons and embeds a fallback theme containing only those icons.
"""

import argparse
import shutil
from pathlib import Path

# icons needed
DEFAULT_ICONS = [
    # Sidebar navigation
    "computer",
    "network-wired",
    "utilities-system-monitor",
    # WebSocket UI
    "network-connect",
    "network-disconnect",
    "arrow-down",
    # Kirigami / dialog / status
    "dialog-warning",
    "dialog-information",
    "emblem-error",
    "emblem-warning",
    "emblem-information",
    "emblem-checked",
    "window-close",
    "dialog-cancel",
    "dialog-warning",
    "document-close",
    "view-close",
    "view-refresh",
    "configure",
    "edit-clear",
    "document-save",
    "document-open",
    "media-record",
    "folder",
    "folder-open",
    "text-csv",
    "network-server",
    "edit-undo",
    "edit-rename",
    "edit-delete",
    "edit-download",
    "search",
    "search-symbolic",
    "notifications",
    "keyframe-record",
    "view-hidden",
    "process-stop",
    "camera-video",
    # Split view & popout windows
    "window-new",
    "view-split-left-right",
    "window-duplicate",
    "view-restore",
    "go-previous",
    "go-next",
    # Toolbar & graph helpers
    "view-filter",
    "download",
    "chronometer",
    "measure",
]

SEARCH_THEMES = [
    Path.home() / ".local/share/icons/kora",
    Path("/usr/share/icons/breeze-dark"),
    Path("/usr/share/icons/breeze"),
    Path("/usr/share/icons/hicolor"),
]

# Icons that should prefer colorful scalable variants (sidebar views, places, etc.)
COLORFUL_SCALABLE_PREF = {
    "computer": "devices/scalable/computer.svg",
    "network-wired": "devices/scalable/network-wired.svg",
    "utilities-system-monitor": "apps/scalable/utilities-system-monitor.svg",
    "camera-video": "devices/scalable/camera-video.svg",
    "network-server": "devices/scalable/network-server.svg",
    "folder": "places/scalable/folder.svg",
    "folder-open": "places/scalable/folder-open.svg",
    "text-csv": "mimetypes/scalable/text-csv.svg",
    "dialog-information": "status/scalable/dialog-information.svg",
    "dialog-warning": "status/scalable/dialog-warning.svg",
    "emblem-checked": "emblems/scalable/emblem-checked.svg",
    "emblem-error": "emblems/scalable/emblem-error.svg",
    "emblem-information": "emblems/scalable/emblem-information.svg",
    "emblem-warning": "emblems/scalable/emblem-warning.svg",
}


def find_system_themes(custom_path: Path | None = None) -> list[Path]:
    themes: list[Path] = []
    if custom_path and custom_path.exists():
        themes.append(custom_path)
    for cand in SEARCH_THEMES:
        if cand.exists() and (cand / "index.theme").exists() and cand not in themes:
            themes.append(cand)
    return themes


def normalize_svg_dimensions(svg_text: str) -> str:
    """Replaces width='100%' height='100%' with explicit viewBox pixel dimensions."""
    import re

    m = re.search(r'viewBox="0\s+0\s+(\d+)\s+(\d+)"', svg_text)
    if m and ('width="100%"' in svg_text or 'height="100%"' in svg_text):
        w, h = m.group(1), m.group(2)
        svg_text = svg_text.replace('width="100%"', f'width="{w}"').replace(
            'height="100%"', f'height="{h}"'
        )
    return svg_text


def convert_svg_to_light(svg_text: str) -> str:
    """Converts dark-theme monochrome foreground colors (#fcfcfc/#dfdfdf/#eff0f1) to Breeze light (#232629)."""
    import re

    light_text = "#232629"
    # Replace .ColorScheme-Text { color: ... }
    svg_text = re.sub(
        r"(\.ColorScheme-Text\s*\{\s*color\s*:\s*)#[0-9a-fA-F]{3,6}(\s*;?\s*\})",
        rf"\g<1>{light_text}\g<2>",
        svg_text,
    )
    # Replace hardcoded monochrome dark-mode fills (#dfdfdf, #fcfcfc, #eff0f1)
    for dark_hex in ("#dfdfdf", "#DFDFDF", "#fcfcfc", "#FCFCFC", "#eff0f1", "#EFF0F1"):
        svg_text = svg_text.replace(f'fill="{dark_hex}"', f'fill="{light_text}"')
        svg_text = svg_text.replace(f"fill:{dark_hex}", f"fill:{light_text}")
    return svg_text


def write_index_theme(theme_dir: Path, theme_name: str) -> list[str]:
    subdirs = set()
    for svg_file in theme_dir.rglob("*.svg"):
        rel_parent = svg_file.parent.relative_to(theme_dir).as_posix()
        if rel_parent != ".":
            subdirs.add(rel_parent)

    sorted_dirs = sorted(subdirs)
    lines = [
        "[Icon Theme]",
        f"Name={theme_name}",
        "Comment=Minimal application fallback icon theme",
        f"Directories={','.join(sorted_dirs)}",
        "",
    ]

    for rel_dir in sorted_dirs:
        parts = rel_dir.replace("\\", "/").split("/")
        category = parts[0]
        if len(parts) > 1 and parts[1].split("@")[0].isdigit():
            size = int(parts[1].split("@")[0])
        else:
            size = 22

        lines.append(f"[{rel_dir}]")
        lines.append(f"Size={size}")
        lines.append(f"Context={category.capitalize()}")
        lines.append("Type=Scalable")
        lines.append("MinSize=8")
        lines.append("MaxSize=512")
        lines.append("")

    index_theme_path = theme_dir / "index.theme"
    index_theme_path.write_text("\n".join(lines), encoding="utf-8")
    return sorted_dirs


def populate_fallback_theme(
    icon_names: list[str],
    output_dir: Path,
    source_dir: Path | None = None,
    theme_name: str = "breeze-fallback",
) -> None:
    system_themes = find_system_themes(source_dir)
    print(f"[Icon Populator] Available system themes: {[str(t) for t in system_themes]}")
    print(f"[Icon Populator] Target directory:        {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy any missing icons from available system themes without wiping existing curated icons
    for name in dict.fromkeys(icon_names):
        existing = [p for p in output_dir.rglob(f"{name}.svg") if "flat" not in p.parts]
        if not existing:
            for sys_theme in system_themes:
                matches = list(sys_theme.rglob(f"{name}.svg"))
                if matches:
                    for match in matches:
                        rel = match.relative_to(sys_theme)
                        dest = output_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(match, dest)
                    break

    # Remove unintended collisions where action/device icons had unrelated matches
    unwanted_collisions = [
        output_dir / "apps/scalable/download.svg",
        output_dir / "apps/scalable/network-wired.svg",
        output_dir / "apps/scalable/search.svg",
        output_dir / "apps/scalable/window-duplicate.svg",
        output_dir / "panel/16/network-wired.svg",
        output_dir / "panel/22/network-wired.svg",
        output_dir / "panel/24/network-wired.svg",
        output_dir / "status/22/network-wired.svg",
        output_dir / "status/24/network-wired.svg",
        output_dir / "devices/16/computer.svg",
        output_dir / "devices/22/computer.svg",
        output_dir / "devices/24/computer.svg",
        output_dir / "devices/64/computer.svg",
        output_dir / "devices/16/network-wired.svg",
        output_dir / "devices/22/network-wired.svg",
        output_dir / "devices/24/network-wired.svg",
    ]
    for uw in unwanted_collisions:
        if uw.exists():
            uw.unlink()

    # Ensure every actions/16 icon is also available in actions/22 and actions/24
    actions_16 = output_dir / "actions" / "16"
    if actions_16.exists():
        for sz in ("22", "24"):
            target_sz_dir = output_dir / "actions" / sz
            target_sz_dir.mkdir(parents=True, exist_ok=True)
            for svg_16 in actions_16.glob("*.svg"):
                dest_sz = target_sz_dir / svg_16.name
                if not dest_sz.exists():
                    shutil.copy2(svg_16, dest_sz)

    # Normalize SVG dimensions across all SVGs in output_dir
    for svg_file in output_dir.rglob("*.svg"):
        raw = svg_file.read_text(encoding="utf-8")
        norm = normalize_svg_dimensions(raw)
        if norm != raw:
            svg_file.write_text(norm, encoding="utf-8")

    # Populate flat/ directory with canonical SVG for each icon
    flat_dir = output_dir / "flat"
    flat_dir.mkdir(parents=True, exist_ok=True)
    found_icons = set()
    for name in dict.fromkeys(icon_names):
        preferred_rel = COLORFUL_SCALABLE_PREF.get(name)
        chosen: Path | None = None
        if preferred_rel and (output_dir / preferred_rel).exists():
            chosen = output_dir / preferred_rel
        else:
            for cand_sub in (
                f"actions/16/{name}.svg",
                f"actions/22/{name}.svg",
                f"actions/24/{name}.svg",
                f"actions/symbolic/{name}.svg",
                f"panel/16/{name}.svg",
                f"devices/scalable/{name}.svg",
                f"apps/scalable/{name}.svg",
                f"places/scalable/{name}.svg",
                f"mimetypes/scalable/{name}.svg",
                f"status/scalable/{name}.svg",
                f"emblems/scalable/{name}.svg",
            ):
                if (output_dir / cand_sub).exists():
                    chosen = output_dir / cand_sub
                    break
            if chosen is None:
                matches = [p for p in output_dir.rglob(f"{name}.svg") if "flat" not in p.parts]
                if matches:
                    chosen = sorted(matches)[0]
        if chosen is not None:
            found_icons.add(name)
            shutil.copy2(chosen, flat_dir / f"{name}.svg")
        else:
            print(f"  [WARNING] Icon '{name}' not found in {output_dir}")

    sorted_dirs = write_index_theme(output_dir, theme_name)

    # Generate corresponding light variant theme (breeze-fallback-light)
    light_theme_name = f"{theme_name}-light"
    light_output_dir = output_dir.parent / light_theme_name
    if light_output_dir.exists():
        shutil.rmtree(light_output_dir)
    shutil.copytree(output_dir, light_output_dir)
    for svg_file in light_output_dir.rglob("*.svg"):
        raw = svg_file.read_text(encoding="utf-8")
        light_svg = convert_svg_to_light(raw)
        if light_svg != raw:
            svg_file.write_text(light_svg, encoding="utf-8")
    write_index_theme(light_output_dir, light_theme_name)

    total_bytes = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
    print("\n[Icon Populator] Summary:")
    print(f"  Icons requested: {len(set(icon_names))}")
    print(f"  Icons found:     {len(found_icons)} / {len(set(icon_names))}")
    print(f"  Subdirectories:  {len(sorted_dirs)}")
    print(f"  Dark theme dir:  {output_dir} ({total_bytes / 1024:.2f} KB)")
    print(f"  Light theme dir: {light_output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Populate minimal Breeze fallback icon theme (dark + light) for packaging."
    )
    parser.add_argument(
        "icons",
        nargs="*",
        default=DEFAULT_ICONS,
        help="List of icon names to embed (default: built-in list of app icons).",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Path to host Breeze theme directory (default: auto-detect /usr/share/icons/breeze-dark).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "contents"
        / "icons"
        / "breeze-fallback",
        help="Output directory (default: contents/icons/breeze-fallback).",
    )
    parser.add_argument(
        "--theme-name",
        type=str,
        default="breeze-fallback",
        help="Name of the fallback theme (default: breeze-fallback).",
    )

    args = parser.parse_args()
    populate_fallback_theme(
        icon_names=args.icons,
        output_dir=args.output,
        source_dir=args.source,
        theme_name=args.theme_name,
    )


if __name__ == "__main__":
    main()

