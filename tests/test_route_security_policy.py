import ast
from pathlib import Path
import unittest


ROUTERS_DIR = Path(__file__).resolve().parents[1] / "app" / "routers"

EXPECTED_ROLES = {
    "admin.py": {"admin", "supervisor"},
    "campanas.py": {"admin", "supervisor", "operador_inscripciones"},
    "catalogos.py": {
        "admin",
        "supervisor",
        "operador_inscripciones",
        "operador_diplomas",
        "coordinador_campana",
    },
    "diplomas.py": {"admin", "supervisor", "operador_diplomas"},
    "personas.py": {"admin", "supervisor", "operador_inscripciones", "operador_diplomas"},
    "reportes.py": {"admin", "supervisor", "operador_inscripciones", "operador_diplomas"},
    "resumen.py": {"admin", "supervisor"},
    "usuarios.py": {"admin"},
}


def protected_router_roles(filename: str) -> set[str]:
    tree = ast.parse((ROUTERS_DIR / filename).read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "router" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        for keyword in node.value.keywords:
            if keyword.arg != "dependencies":
                continue
            for call in ast.walk(keyword.value):
                if not isinstance(call, ast.Call):
                    continue
                if isinstance(call.func, ast.Name) and call.func.id == "require_roles":
                    return {
                        argument.value
                        for argument in call.args
                        if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
                    }
    return set()


class RouteSecurityPolicyTests(unittest.TestCase):
    def test_sensitive_routers_require_the_expected_roles(self) -> None:
        for filename, expected_roles in EXPECTED_ROLES.items():
            with self.subTest(router=filename):
                self.assertEqual(protected_router_roles(filename), expected_roles)

    def test_only_explicitly_public_routers_lack_a_router_role_guard(self) -> None:
        unguarded = {
            path.name
            for path in ROUTERS_DIR.glob("*.py")
            if path.name != "__init__.py" and not protected_router_roles(path.name)
        }
        self.assertEqual(unguarded, {"auth.py", "health.py", "publico.py"})

    def test_authenticated_profile_endpoint_keeps_its_user_guard(self) -> None:
        source = (ROUTERS_DIR / "auth.py").read_text(encoding="utf-8")
        self.assertIn("Depends(get_current_user)", source)

    def test_campaign_creation_has_a_stricter_write_guard(self) -> None:
        source = (ROUTERS_DIR / "campanas.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        create_function = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "crear_campana"
        )
        role_calls = [
            call
            for call in ast.walk(create_function)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "require_roles"
        ]
        self.assertEqual(len(role_calls), 1)
        self.assertEqual(
            {argument.value for argument in role_calls[0].args if isinstance(argument, ast.Constant)},
            {"admin", "operador_inscripciones"},
        )


if __name__ == "__main__":
    unittest.main()
