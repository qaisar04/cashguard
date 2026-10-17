"""Pre-fetches model weights so the service runs with HF_HUB_OFFLINE=1 (no internet inside the bank's network)."""
from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download

from app.settings import DEFAULT_CONFIG, load_pipeline_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--cache-dir", type=Path, default=None, help="HF cache dir (default: ~/.cache/huggingface)")
    args = parser.parse_args()
    cfg = load_pipeline_config(args.config)
    models = [d.model for d in cfg.detectors] + ([cfg.screen.clip_model] if cfg.screen.enabled else [])
    for model in models:
        path = snapshot_download(model, cache_dir=args.cache_dir, allow_patterns=["*.json", "*.txt", "*.safetensors"])
        print(f"{model} -> {path}")


if __name__ == "__main__":
    main()
