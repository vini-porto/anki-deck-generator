# template/__init__.py
# Registers all available card templates.

from template import dark, light, minimal, immersive

AVAILABLE = {
    "dark":      dark,
    "light":     light,
    "minimal":   minimal,
    "immersive": immersive,
}


def load(name: str):
    """
    Load a template module by name.
    Raises ValueError if the template is not found.
    """
    if name not in AVAILABLE:
        raise ValueError(
            f"Unknown template '{name}'. "
            f"Available: {', '.join(AVAILABLE.keys())}"
        )
    return AVAILABLE[name]
