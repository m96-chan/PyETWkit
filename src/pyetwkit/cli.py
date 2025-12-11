"""Command-line interface for PyETWkit.

This module provides a CLI tool for monitoring ETW events from the command line.
"""

from __future__ import annotations

import json
import sys

import click

from pyetwkit import __version__


@click.group()
@click.version_option(version=__version__, prog_name="pyetwkit")
def main() -> None:
    """PyETWkit - High-performance ETW consumer for Python.

    Monitor Windows ETW events from the command line.

    Examples:

        # List available providers
        pyetwkit providers

        # Search for providers
        pyetwkit providers --search Kernel

        # List available profiles
        pyetwkit profiles

        # Listen to events (requires admin)
        pyetwkit listen Microsoft-Windows-Kernel-Process
    """
    pass


@main.command()
@click.option("--search", "-s", help="Search for providers by name")
@click.option("--limit", "-n", default=50, help="Maximum number of providers to show")
@click.option(
    "--format", "-f", "output_format", type=click.Choice(["table", "json"]), default="table"
)
def providers(search: str | None, limit: int, output_format: str) -> None:
    """List available ETW providers.

    Shows registered ETW providers on the system. Use --search to filter
    by name.

    Examples:

        pyetwkit providers
        pyetwkit providers --search Kernel
        pyetwkit providers --format json
    """
    try:
        from pyetwkit._core import list_providers, search_providers
    except ImportError:
        click.echo("Error: Native extension not available", err=True)
        sys.exit(1)

    provider_list = search_providers(search) if search else list_providers()

    # Limit results
    provider_list = provider_list[:limit]

    if output_format == "json":
        data = [{"name": p.name, "guid": p.guid, "source": p.source} for p in provider_list]
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"{'Name':<60} {'GUID':<38} Source")
        click.echo("-" * 110)
        for p in provider_list:
            click.echo(f"{p.name[:59]:<60} {p.guid:<38} {p.source}")

    if not search:
        total = len(list_providers())
        click.echo(f"\nShowing {len(provider_list)} of {total} providers")


@main.command()
@click.option(
    "--format", "-f", "output_format", type=click.Choice(["table", "json"]), default="table"
)
def profiles(output_format: str) -> None:
    """List available provider profiles.

    Profiles are pre-configured sets of providers for common use cases
    like audio monitoring, network analysis, etc.

    Examples:

        pyetwkit profiles
        pyetwkit profiles --format json
    """
    from pyetwkit.profiles import list_profiles

    profile_list = list_profiles()

    if output_format == "json":
        data = [
            {
                "name": p.name,
                "description": p.description,
                "providers": [pr.name for pr in p.providers],
            }
            for p in profile_list
        ]
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"{'Profile':<15} {'Description':<50} Providers")
        click.echo("-" * 80)
        for p in profile_list:
            provider_count = len(p.providers)
            click.echo(f"{p.name:<15} {p.description[:49]:<50} {provider_count}")


@main.command()
@click.argument("provider", required=False)
@click.option("--profile", "-p", help="Use a provider profile")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "jsonl"]),
    default="table",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--max-events", "-n", type=int, help="Maximum number of events to capture")
@click.option(
    "--level",
    "-l",
    type=click.Choice(["critical", "error", "warning", "info", "verbose"]),
    default="info",
)
def listen(
    provider: str | None,
    profile: str | None,
    output_format: str,
    output: str | None,
    max_events: int | None,
    level: str,
) -> None:
    """Listen to ETW events from a provider or profile.

    Requires administrator privileges to start ETW sessions.

    Examples:

        # Listen to a specific provider
        pyetwkit listen Microsoft-Windows-Kernel-Process

        # Use a profile
        pyetwkit listen --profile audio

        # Output to file
        pyetwkit listen --profile network --output events.jsonl --format jsonl

        # Limit events
        pyetwkit listen Microsoft-Windows-DNS-Client --max-events 100
    """
    if not provider and not profile:
        click.echo("Error: Please specify a provider or --profile", err=True)
        click.echo("Usage: pyetwkit listen PROVIDER or pyetwkit listen --profile PROFILE", err=True)
        sys.exit(1)

    # Import here to avoid import errors when just showing help
    try:
        from pyetwkit._core import EtwProvider, EtwSession
    except ImportError:
        click.echo("Error: Native extension not available", err=True)
        sys.exit(1)

    # Get providers from profile or direct specification
    providers_to_use = []
    if profile:
        from pyetwkit.profiles import get_profile

        prof = get_profile(profile)
        if prof is None:
            click.echo(f"Error: Profile '{profile}' not found", err=True)
            sys.exit(1)
        for pc in prof.providers:
            providers_to_use.append((pc.name, pc.guid or pc.name))
    else:
        providers_to_use.append((provider, provider))

    click.echo(f"Starting ETW session with {len(providers_to_use)} provider(s)...")
    click.echo("Press Ctrl+C to stop\n")

    # Level mapping
    level_map = {
        "critical": 1,
        "error": 2,
        "warning": 3,
        "info": 4,
        "verbose": 5,
    }

    try:
        session = EtwSession("PyETWkitCLI")

        for name, guid_or_name in providers_to_use:
            prov = EtwProvider(guid_or_name, name)
            prov = prov.with_level(level_map.get(level, 4))
            session.add_provider(prov)

        session.start()

        event_count = 0
        output_file = None

        try:
            if output:
                output_file = open(output, "w", encoding="utf-8")  # noqa: SIM115

            while True:
                if max_events and event_count >= max_events:
                    break

                event = session.next_event_timeout(1000)  # 1 second timeout
                if event is None:
                    continue

                event_count += 1

                # Format event
                if output_format in ("json", "jsonl"):
                    line = json.dumps(event.to_dict(), default=str)
                else:
                    line = f"[{event.timestamp}] {event.provider_name or event.provider_id} Event {event.event_id}"

                if output_file:
                    output_file.write(line + "\n")
                    output_file.flush()
                else:
                    click.echo(line)

        except KeyboardInterrupt:
            click.echo(f"\nStopped. Captured {event_count} events.")
        finally:
            if output_file:
                output_file.close()
            session.stop()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Note: ETW sessions require administrator privileges", err=True)
        sys.exit(1)


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), required=True, help="Output file path")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["csv", "json", "jsonl", "parquet"]),
    default="csv",
    help="Output format",
)
@click.option("--provider", "-p", multiple=True, help="Filter by provider name or GUID")
@click.option("--event-id", "-e", multiple=True, type=int, help="Filter by event ID")
@click.option("--limit", "-n", type=int, help="Maximum number of events to export")
def export(
    input_file: str,
    output: str,
    output_format: str,
    provider: tuple[str, ...],
    event_id: tuple[int, ...],
    limit: int | None,
) -> None:
    """Export ETL file to various formats.

    Reads an ETL (Event Trace Log) file and exports events to CSV, JSON,
    JSONL, or Parquet format.

    Examples:

        # Export to CSV
        pyetwkit export trace.etl -o events.csv

        # Export to Parquet
        pyetwkit export trace.etl -o events.parquet -f parquet

        # Filter by provider
        pyetwkit export trace.etl -o filtered.csv -p Microsoft-Windows-Kernel-Process

        # Export first 1000 events
        pyetwkit export trace.etl -o sample.json -f json --limit 1000
    """
    try:
        from pyetwkit._core import EtlReader
    except ImportError:
        click.echo("Error: Native extension not available", err=True)
        sys.exit(1)

    click.echo(f"Reading ETL file: {input_file}")

    try:
        reader = EtlReader(input_file)
        events = []
        count = 0

        for event in reader.events():
            # Apply filters
            if provider:
                event_provider = event.provider_name or str(event.provider_id)
                if not any(p.lower() in event_provider.lower() for p in provider):
                    continue

            if event_id and event.event_id not in event_id:
                continue

            events.append(event)
            count += 1

            if limit and count >= limit:
                break

            if count % 10000 == 0:
                click.echo(f"  Processed {count} events...")

        click.echo(f"Collected {len(events)} events")

        if not events:
            click.echo("No events to export")
            return

        # Export based on format
        click.echo(f"Exporting to {output}...")

        if output_format == "csv":
            from pyetwkit.export import to_csv

            to_csv(events, output)
        elif output_format == "json":
            from pyetwkit.export import to_json

            to_json(events, output)
        elif output_format == "jsonl":
            from pyetwkit.export import to_jsonl

            to_jsonl(events, output)
        elif output_format == "parquet":
            from pyetwkit.export import to_parquet

            to_parquet(events, output)

        click.echo(f"Exported {len(events)} events to {output}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
