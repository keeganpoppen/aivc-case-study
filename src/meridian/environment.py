"""Load local runtime settings without searching outside the selected project."""

from pathlib import Path

from dotenv import load_dotenv


def load_environment(root: Path) -> None:
    # Exported values (including an explicitly empty value) take precedence.
    load_dotenv(dotenv_path=root / ".env", override=False)
