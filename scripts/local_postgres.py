"""Provision an isolated loopback-only development cluster, never touch existing service."""

import os
import secrets
import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
data = root / "data" / "postgres"
flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def run(args):
    r = subprocess.run(
        [str(x) for x in args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        timeout=120,
    )
    if r.returncode:
        raise RuntimeError(
            "PostgreSQL setup command failed; inspect local data/postgres logs. No credentials logged."
        )


def main():
    env = root / ".env"
    if data.exists():
        print(
            "Existing isolated cluster preserved. Use its stored connection configuration."
        )
        return
    initdb = shutil.which("initdb")
    pg_ctl = shutil.which("pg_ctl")
    if not initdb or not pg_ctl:
        raise RuntimeError("Install PostgreSQL and add initdb and pg_ctl to PATH.")
    if not env.exists():
        raise RuntimeError("Run uv run python -m app.bootstrap first.")
    password = secrets.token_urlsafe(30)
    pw = root / "data" / "pg-bootstrap.secret"
    pw.parent.mkdir(exist_ok=True)
    pw.write_text(password, encoding="utf-8")
    try:
        run(
            [
                initdb,
                "-D",
                data,
                "-U",
                "neurotwin_owner",
                "--auth=scram-sha-256",
                "--pwfile",
                pw,
                "--encoding=UTF8",
                "--locale=C",
            ]
        )
    finally:
        pw.unlink(missing_ok=True)
    # Persist the connection before starting so a process interruption is recoverable.
    text = env.read_text(encoding="utf-8")
    lines = [x for x in text.splitlines() if not x.startswith("DATABASE_URL=")]
    lines.append(
        f"DATABASE_URL=postgresql+psycopg://neurotwin_owner:{password}@127.0.0.1:55439/neurotwin"
    )
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Only this dedicated cluster, on a distinct loopback port, is started.
    run(
        [
            pg_ctl,
            "-D",
            data,
            "-l",
            root / "data" / "postgres.log",
            "-o",
            "-h 127.0.0.1 -p 55439",
            "-w",
            "start",
        ]
    )
    import psycopg

    with psycopg.connect(
        host="127.0.0.1",
        port=55439,
        user="neurotwin_owner",
        password=password,
        dbname="postgres",
        autocommit=True,
    ) as conn:
        conn.execute("CREATE DATABASE neurotwin")
    print(
        "Isolated development PostgreSQL created at loopback port 55439; credentials stored only in .env. Owner role is local-development only."
    )


if __name__ == "__main__":
    main()
