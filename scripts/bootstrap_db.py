"""Workspace-only PostgreSQL. No Windows service, registry or PATH changes."""
from pathlib import Path
import os
import secrets
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
runtime = ROOT / ".runtime"
pg = runtime / "pgsql"
data = runtime / "pgdata"


def run(*args):
    subprocess.run([str(a) for a in args], check=True, creationflags=subprocess.CREATE_NO_WINDOW)


def main():
    runtime.mkdir(exist_ok=True)
    if not (pg / "bin" / "initdb.exe").exists():
        archive = runtime / "postgres-portable.zip"
        if not archive.exists(): raise SystemExit("Download the official EDB PostgreSQL Windows binaries ZIP to .runtime/postgres-portable.zip first")
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                parts = Path(name).parts
                if len(parts) > 1 and parts[0] == "pgsql" and parts[1] in ("bin", "lib", "share"):
                    z.extract(name, runtime)
    password_file = runtime / "bootstrap-password"
    if not data.exists():
        password_file.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        run(pg/"bin"/"initdb.exe", "-D", data, "-U", "postgres", "-E", "UTF8", "--locale=C", "-A", "scram-sha-256", f"--pwfile={password_file}")
        with (data/"postgresql.conf").open("a") as f:
            f.write("\nlisten_addresses = '127.0.0.1'\nport = 55432\n")
    status = subprocess.run([str(pg/"bin"/"pg_ctl.exe"), "status", "-D", str(data)], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if status.returncode != 0:
        run(pg/"bin"/"pg_ctl.exe", "start", "-D", data, "-l", runtime/"postgres.log", "-w")
    import psycopg
    from psycopg import sql
    envfile = ROOT / ".env"
    if not envfile.exists():
        password = secrets.token_urlsafe(24)
        with psycopg.connect(host="127.0.0.1", port=55432, user="postgres", password=password_file.read_text(), dbname="postgres", autocommit=True) as conn:
            if conn.execute("SELECT 1 FROM pg_roles WHERE rolname = 'safeops'").fetchone():
                raise SystemExit("Existing safeops role found; refusing to change its credentials. Configure .env manually.")
            conn.execute(sql.SQL("CREATE ROLE safeops LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(sql.Literal(password)))
            conn.execute("CREATE DATABASE safeops OWNER safeops")
        envfile.write_text(f"DATABASE_URL=postgresql+psycopg://safeops:{password}@127.0.0.1:55432/safeops\nSESSION_SECRET={secrets.token_urlsafe(48)}\nDEMO_PASSWORD=SafeOps-local-demo\nCORS_ORIGIN=http://localhost:3000\n", encoding="utf-8")
    print("Workspace PostgreSQL ready on 127.0.0.1:55432. Environment saved in ignored .env; credentials were not printed.")


if __name__ == "__main__": main()
