"""Convert mermaid diagrams in markdown files to SVG images.

Usage:
    python mermaid_to_svg.py input.md -o output.svg

Prerequisites:
    mermaid-cli installed: npm install -g @mermaid-js/mermaid-cli
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Stage colors for inline styling (Qt QSvgWidget doesn't support CSS class selectors)
STAGE_COLORS = {
    "concept": {"fill": "#66CC00", "stroke": "#52A300"},
    "planning": {"fill": "#00CC66", "stroke": "#00A352"},
    "implementing": {"fill": "#00CCCC", "stroke": "#00A3A3"},
    "testing": {"fill": "#0099CC", "stroke": "#007AA3"},
    "releasing": {"fill": "#0066CC", "stroke": "#0052A3"},
    "shipped": {"fill": "#0033CC", "stroke": "#0029A3"},
}


def extract_mermaid(markdown_path: Path) -> str:
    """Extract mermaid code block from markdown file."""
    content = markdown_path.read_text(encoding="utf-8")
    match = re.search(r"```mermaid\s*\n(.*?)```", content, re.DOTALL)
    if not match:
        raise ValueError(f"No mermaid code block found in {markdown_path}")
    return match.group(1)


def apply_inline_styles(svg_content: str) -> str:
    """Apply inline fill/stroke attributes to elements with stage classes.

    Qt's QSvgWidget has limited CSS support and doesn't handle class selectors
    like '.concept>*'. This function adds inline attributes for compatibility.

    Strategy: Find all <g class="node {stage} ..."> groups, then find the first
    <path> inside them (which is the node background shape) and add fill/stroke.
    """
    # Collect all modifications needed (position, old_text, new_text)
    modifications = []

    for stage, colors in STAGE_COLORS.items():
        fill_color = colors["fill"]
        stroke_color = colors["stroke"]

        # Find all groups with this stage class
        stage_pattern = rf'<g[^>]*class="node {stage} statediagram-state"[^>]*>'

        for group_match in re.finditer(stage_pattern, svg_content):
            group_end_tag = group_match.end()

            # Find the first <path after this group opening tag
            # The path is the background shape inside <g class="basic label-container">
            search_area = svg_content[group_end_tag : group_end_tag + 2000]
            path_match = re.search(r"<path\b([^>]*)(/?>)", search_area)

            if path_match:
                path_start = group_end_tag + path_match.start()
                path_end = group_end_tag + path_match.end()
                path_attrs = path_match.group(1)
                path_close = path_match.group(2)

                # Build new path tag with fill and stroke
                new_attrs = path_attrs
                if 'fill="' not in new_attrs:
                    new_attrs = f' fill="{fill_color}"' + new_attrs
                if 'stroke="' not in new_attrs:
                    new_attrs = f' stroke="{stroke_color}"' + new_attrs

                new_path_tag = f"<path{new_attrs}{path_close}"
                old_path_tag = path_match.group(0)

                if new_path_tag != old_path_tag:
                    modifications.append((path_start, path_end, new_path_tag))

    # Apply modifications from end to beginning to preserve positions
    modifications.sort(key=lambda x: x[0], reverse=True)
    for start, end, new_text in modifications:
        svg_content = svg_content[:start] + new_text + svg_content[end:]

    return svg_content


def convert_to_svg(mermaid_content: str, output_path: Path) -> None:
    """Convert mermaid content to SVG using mmdc."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".mmd", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(mermaid_content)
        tmp_path = Path(tmp.name)

    try:
        # Use shell=True on Windows to find mmdc.cmd in PATH
        result = subprocess.run(
            ["mmdc", "-i", str(tmp_path), "-o", str(output_path)],
            capture_output=True,
            text=True,
            shell=(sys.platform == "win32"),
        )
        if result.returncode != 0:
            raise RuntimeError(f"mmdc failed: {result.stderr}")

        # Post-process SVG to add inline styles for Qt compatibility
        svg_content = output_path.read_text(encoding="utf-8")
        svg_content = apply_inline_styles(svg_content)
        output_path.write_text(svg_content, encoding="utf-8")

    finally:
        tmp_path.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Convert mermaid diagrams in markdown to SVG"
    )
    parser.add_argument("input", type=Path, help="Input markdown file")
    parser.add_argument("-o", "--output", type=Path, help="Output SVG file")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    output = args.output or args.input.with_suffix(".svg")
    output.parent.mkdir(parents=True, exist_ok=True)

    mermaid_content = extract_mermaid(args.input)
    convert_to_svg(mermaid_content, output)
    print(f"Generated: {output}")


if __name__ == "__main__":
    main()
