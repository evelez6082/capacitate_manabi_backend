from __future__ import annotations

import argparse
from getpass import getpass
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings
from app.security import hash_password


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea o actualiza un usuario admin/supervisor.")
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--password",
        help="Contraseña. Omítela para leer CAPACITATE_ADMIN_PASSWORD o solicitarla sin eco.",
    )
    parser.add_argument("--name", default="Supervisor")
    parser.add_argument("--role", default="supervisor", choices=["admin", "supervisor", "operador_inscripciones"])
    args = parser.parse_args()
    password = args.password or os.getenv("CAPACITATE_ADMIN_PASSWORD") or getpass("Contraseña: ")
    if len(password) < 12:
        parser.error("la contraseña debe tener al menos 12 caracteres")

    settings = get_settings()
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        role_names = {
            "admin": "Administrador",
            "supervisor": "Supervisor",
            "operador_inscripciones": "Operador de inscripciones",
        }
        conn.execute(
            """
            INSERT INTO roles (codigo, nombre, descripcion)
            VALUES (%s, %s, %s)
            ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre
            """,
            (args.role, role_names[args.role], "Acceso administrativo al panel."),
        )
        existing_user = conn.execute("SELECT id FROM usuarios WHERE lower(email) = lower(%s)", (args.email,)).fetchone()
        if existing_user:
            user = conn.execute(
                """
                UPDATE usuarios
                SET password_hash = %s,
                    nombre_visible = %s,
                    estado = 'activo',
                    updated_at = now()
                WHERE id = %s
                RETURNING id
                """,
                (hash_password(password), args.name, existing_user["id"]),
            ).fetchone()
        else:
            user = conn.execute(
                """
                INSERT INTO usuarios (email, password_hash, nombre_visible, estado)
                VALUES (%s, %s, %s, 'activo')
                RETURNING id
                """,
                (args.email.lower(), hash_password(password), args.name),
            ).fetchone()
        role = conn.execute("SELECT id FROM roles WHERE codigo = %s", (args.role,)).fetchone()
        conn.execute(
            """
            INSERT INTO usuario_roles (usuario_id, rol_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (user["id"], role["id"]),
        )
        conn.commit()
    print(f"Usuario listo: {args.email} ({args.role})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
