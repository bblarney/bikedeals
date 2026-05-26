import yaml
from pathlib import Path

from scrapers.models import VendorConfig

VENDORS_DIR = Path(__file__).parent / "vendors"


def load_registry() -> list[VendorConfig]:
    configs = []
    for path in sorted(p for p in VENDORS_DIR.glob("*.yaml") if not p.name.startswith("_")):
        with path.open() as f:
            data = yaml.safe_load(f)
        configs.append(VendorConfig(**data))
    return configs
