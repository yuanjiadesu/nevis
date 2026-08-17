import argparse
import asyncio
import json
from dataclasses import asdict

from nevis.application.summaries import get_summary_diagnostics, reconcile_summary_work
from nevis.infrastructure.database import build_engine, build_session_factory
from nevis.settings import get_settings


async def _reconcile(arguments: argparse.Namespace) -> None:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    sessions = build_session_factory(engine)
    try:
        async with sessions() as session:
            result = await reconcile_summary_work(
                session,
                settings,
                dry_run=arguments.dry_run,
                retry_failed=arguments.retry_failed,
                batch_size=arguments.batch_size,
            )
        print(json.dumps(asdict(result), sort_keys=True))
    finally:
        await engine.dispose()


async def _diagnose() -> None:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    sessions = build_session_factory(engine)
    try:
        async with sessions() as session:
            result = await get_summary_diagnostics(session, settings)
        print(json.dumps(asdict(result), sort_keys=True))
    finally:
        await engine.dispose()


def run() -> None:
    parser = argparse.ArgumentParser(prog="nevis-summary-maintenance")
    subcommands = parser.add_subparsers(dest="command", required=True)
    reconcile = subcommands.add_parser("reconcile")
    reconcile.add_argument("--dry-run", action="store_true")
    reconcile.add_argument("--retry-failed", action="store_true")
    reconcile.add_argument("--batch-size", type=int, default=100)
    subcommands.add_parser("diagnose")
    arguments = parser.parse_args()
    if arguments.command == "reconcile":
        asyncio.run(_reconcile(arguments))
    elif arguments.command == "diagnose":
        asyncio.run(_diagnose())


if __name__ == "__main__":
    run()
