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
]

SEARCH_THEMES = [
    # Path("/usr/share/icons/breeze"),
    # Path("/usr/local/share/icons/breeze"),
    Path.home() / ".local/share/icons/kora",
    # Path("/usr/share/icons/breeze-dark"),
    Path("/usr/share/icons/hicolor"),
]


def find_system_theme(custom_path: Path | None = None) -> Path:
    if custom_path and custom_path.exists():
        return custom_path
    for cand in SEARCH_THEMES:
        if cand.exists() and (cand / "index.theme").exists():
            return cand
    raise FileNotFoundError(
        "Could not find a valid freedesktop icon theme on this system. "
        f"Checked: {[str(p) for p in SEARCH_THEMES]}"
    )


def populate_fallback_theme(
    icon_names: list[str],
    output_dir: Path,
    source_dir: Path | None = None,
    theme_name: str = "breeze-fallback",
) -> None:
    source_theme = find_system_theme(source_dir)
    print(f"[Icon Populator] Using source theme: {source_theme}")
    print(f"[Icon Populator] Target directory:  {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    copied_categories_sizes = set()
    found_icons = set()
    total_bytes = 0

    for name in icon_names:
        # Search for .svg first, then .png
        matches = list(source_theme.rglob(f"{name}.svg"))
        if not matches:
            matches = list(source_theme.rglob(f"{name}.png"))

        if not matches:
            print(f"  [WARNING] Icon '{name}' not found in {source_theme}")
            continue

        found_icons.add(name)

        # Copy matches into relative paths
        for match in matches:
            rel = match.relative_to(source_theme)
            dest = output_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(match, dest)
            total_bytes += dest.stat().st_size
            copied_categories_sizes.add(str(rel.parent))

    # Generate freedesktop index.theme
    index_theme_path = output_dir / "index.theme"
    sorted_dirs = sorted(copied_categories_sizes)

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
            size_str = parts[1].split("@")[0]
        else:
            size_str = "22"
        size = int(size_str)

        lines.append(f"[{rel_dir}]")
        lines.append(f"Size={size}")
        lines.append(f"Context={category.capitalize()}")
        lines.append("Type=Threshold")
        lines.append("")

    index_theme_path.write_text("\n".join(lines), encoding="utf-8")

    print("\n[Icon Populator] Summary:")
    print(f"  Icons requested: {len(icon_names)}")
    print(f"  Icons found:     {len(found_icons)} / {len(icon_names)}")
    print(f"  Subdirectories:  {len(sorted_dirs)}")
    print(f"  Total disk size: {total_bytes / 1024:.2f} KB")
    print(f"  Wrote:           {index_theme_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Populate minimal Breeze fallback icon theme for packaging."
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
        help="Path to host Breeze theme directory (default: auto-detect /usr/share/icons/breeze).",
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
