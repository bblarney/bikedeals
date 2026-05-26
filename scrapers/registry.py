import yaml
from pathlib import Path

from scrapers.models import VendorConfig

VENDORS_DIR = Path(__file__).parent / "vendors"


def load_registry() -> list[VendorConfig]:
    configs = []
    for path in sorted(VENDORS_DIR.glob("*.yaml")):
        with path.open() as f:
            data = yaml.safe_load(f)
        configs.append(VendorConfig(**data))
    return configs
