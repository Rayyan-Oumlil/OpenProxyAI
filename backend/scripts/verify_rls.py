#!/usr/bin/env python3
"""Verify PostgreSQL Row-Level Security (RLS) for multi-tenant isolation.

Connects to the database, sets org_id to org A, attempts to read org B's data,
and generates a CSV evidence report for auditors.

Usage:
    python -m scripts.verify_rls
    DATABASE_URL=postgresql+asyncpg://... python -m scripts.verify_rls

Requires:
    - RLS migration (f8a9b0c1d2e3) applied
    - At least two organizations in the database
"""

from __future__ import annotations

import asyncio
import csv
import os
import sys
from datetime import datetime, UTC
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


RLS_TABLES = [
    "request_logs",
    "api_keys",
    "llm_provider_keys",
    "webhook_deliveries",
    "semantic_cache_entries",
    "prompt_templates",
]


async def verify_rls() -> int:
    """Run RLS verification and return exit code (0=pass, 1=fail)."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is required")
        return 1
    engine = create_async_engine(database_url, poolclass=NullPool)

    results: list[dict] = []
    exit_code = 0

    async with engine.connect() as conn:
        # Get two distinct org IDs
        orgs_result = await conn.execute(
            text("SELECT id FROM organizations ORDER BY created_at LIMIT 2")
        )
        org_rows = orgs_result.fetchall()
        if len(org_rows) < 2:
            print("SKIP: Need at least 2 organizations for RLS verification")
            return 0

        org_a = str(org_rows[0][0])
        org_b = str(org_rows[1][0])

        async with conn.begin():
            await conn.execute(
                text("SELECT set_config('app.current_org_id', :org_id, true)"),
                {"org_id": org_a},
            )

            for table in RLS_TABLES:
                count_b_result = await conn.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE org_id = :org_b"),
                    {"org_b": org_b},
                )
                count_b = count_b_result.scalar() or 0

                count_a_result = await conn.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE org_id = :org_a"),
                    {"org_a": org_a},
                )
                count_a = count_a_result.scalar() or 0

                passed = count_b == 0
                if not passed:
                    exit_code = 1

                results.append({
                    "table": table,
                    "org_a": org_a,
                    "org_b": org_b,
                    "rows_leaked": count_b,
                    "org_a_visible": count_a,
                    "passed": passed,
                    "timestamp": datetime.now(UTC).isoformat(),
                })

    await engine.dispose()

    # Write CSV report
    report_path = Path(__file__).parent.parent / "rls_verification_report.csv"
    try:
        with open(report_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "table", "org_a", "org_b", "rows_leaked", "org_a_visible",
                    "passed", "timestamp",
                ],
            )
            writer.writeheader()
            writer.writerows(results)
    except OSError as e:
        print(f"ERROR: Cannot write report: {e}")
        return 1

    print(f"RLS verification report: {report_path}")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  {r['table']}: {status} (org B leaked: {r['rows_leaked']}, org A visible: {r['org_a_visible']})")

    return exit_code


def main() -> None:
    exit_code = asyncio.run(verify_rls())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
