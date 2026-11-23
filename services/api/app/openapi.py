"""Write the API's OpenAPI schema as JSON.

Usage: ``uv run python -m app.openapi [path]``. Writes to stdout without a path.
"""

import json
import sys
from pathlib import Path

from app.main import create_app


def render() -> str:
	"""Render the OpenAPI schema.

	Returns:
		The schema as JSON with sorted keys.
	"""
	return json.dumps(create_app().openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
	if len(sys.argv) > 1:
		Path(sys.argv[1]).write_text(render(), encoding="utf-8", newline="\n")
	else:
		sys.stdout.write(render())
