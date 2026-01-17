"""
Web UI for Czech Grants Actor (Apify Standby Mode).

Provides a beautiful web interface to browse ALL grants from the czech-grants dataset,
aggregating data from all ministries (MZ, MZV, MŽP, etc.).
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime

import aiohttp_jinja2
import jinja2
from aiohttp import web
from apify import Actor


def is_date_in_past(date_str: str) -> bool:
    """
    Check if a date string (YYYY-MM-DD) is in the past.

    Args:
        date_str: Date in ISO format (YYYY-MM-DD)

    Returns:
        True if date is in the past, False otherwise
    """
    if not date_str:
        return False

    try:
        date = datetime.fromisoformat(date_str)
        return date.date() < datetime.now().date()
    except (ValueError, TypeError):
        return False


async def handle_index(request):
    """Main page handler - displays ALL grants from czech-grants dataset"""
    # Load ALL grants from czech-grants dataset (no limit)
    dataset = await Actor.open_dataset(name='czech-grants')
    data = await dataset.get_data()  # Load all records
    all_grants = data.items or []

    Actor.log.info(f"Loaded {len(all_grants)} grants from dataset")

    # Calculate statistics across ALL sources
    stats = calculate_statistics(all_grants)

    # Get unique source IDs for filter dropdown
    sources = list(set(g.get('sourceId') for g in all_grants if g.get('sourceId')))
    sources.sort()

    # Get current timestamp for footer
    current_time = datetime.now().strftime('%d.%m.%Y %H:%M')

    return aiohttp_jinja2.render_template(
        'index.html',
        request,
        {
            'grants': all_grants,
            'stats': stats,
            'sources': sources,
            'current_time': current_time,
        }
    )


async def handle_health(request):
    """Health check + Apify readiness probe"""
    if 'x-apify-container-server-readiness-probe' in request.headers:
        Actor.log.info('Readiness probe received')
        return web.Response(text='Ready', status=200)
    return web.Response(text='OK', status=200)


def calculate_statistics(grants):
    """Calculate dashboard statistics for ALL grants"""
    total_count = len(grants)

    # Sum max funding amounts
    total_funding = sum(
        g.get('fundingAmount', {}).get('max', 0)
        for g in grants
    )

    # Average funding
    avg_funding = total_funding / total_count if total_count > 0 else 0

    # Status breakdown
    status_counts = {
        'ok': len([g for g in grants if g.get('status') == 'ok']),
        'partial': len([g for g in grants if g.get('status') == 'partial']),
        'error': len([g for g in grants if g.get('status') == 'error']),
    }

    # Active grants (deadline in future)
    active_count = len([
        g for g in grants
        if g.get('deadline') and not is_date_in_past(g.get('deadline'))
    ])

    # Per-source breakdown
    source_counts = {}
    for grant in grants:
        source_id = grant.get('sourceId', 'unknown')
        source_counts[source_id] = source_counts.get(source_id, 0) + 1

    return {
        'total_count': total_count,
        'active_count': active_count,
        'total_funding': total_funding,
        'avg_funding': avg_funding,
        'status_counts': status_counts,
        'source_counts': source_counts,
    }


async def start_web_server():
    """Start aiohttp web server for Standby mode"""
    # Get port from environment variable with fallback
    port_str = os.getenv('APIFY_CONTAINER_PORT') or os.getenv('PORT') or '8080'

    try:
        port = int(port_str)
    except ValueError:
        raise ValueError(f"Invalid port number: {port_str}")

    Actor.log.info(f"Starting web UI on port {port}")

    # Create app
    app = web.Application()

    # Setup Jinja2
    template_dir = Path(__file__).parent / 'templates'
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(str(template_dir)))
    env = aiohttp_jinja2.get_env(app)
    env.globals['is_date_in_past'] = is_date_in_past

    # Routes
    app.router.add_get('/', handle_index)
    app.router.add_get('/health', handle_health)
    app.router.add_static('/static', Path(__file__).parent / 'static')

    # Start server with AppRunner
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    Actor.log.info(f"Web UI running on http://0.0.0.0:{port}")

    # Keep running indefinitely
    await asyncio.Event().wait()
