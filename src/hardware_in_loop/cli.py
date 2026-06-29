"""Command line entry point."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import load_config
from .pipeline import run_hil
from .plugins import load_target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generic Hardware-in-the-Loop runner")
    parser.add_argument("--config", required=True, help="Path to a HIL YAML config")
    parser.add_argument("--tx", default=None, help="Override tx.target, e.g. file.py:generate")
    parser.add_argument("--rx", default=None, help="Override rx.target, e.g. file.py:process")
    parser.add_argument("--dry-run", action="store_true", help="Use software loopback, no instruments")
    parser.add_argument("--run-dir", default=None, help="Optional existing/new run directory")
    parser.add_argument("--log-level", default="INFO", help="Python logging level")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config(args.config)
    if args.tx:
        config.tx.target = args.tx
    if args.rx:
        config.rx.target = args.rx
    if args.dry_run:
        config.run.dry_run = True

    if not config.tx.target:
        parser.error("A TX target is required in config tx.target or --tx")

    tx_plugin = load_target(config.tx.target)
    rx_plugin = load_target(config.rx.target) if config.rx.target else None
    summary = run_hil(
        config=config,
        tx_plugin=tx_plugin,
        rx_plugin=rx_plugin,
        run_dir=Path(args.run_dir) if args.run_dir else None,
    )
    logging.getLogger(__name__).info("Run complete: %s", summary["run_dir"])


if __name__ == "__main__":
    main()
