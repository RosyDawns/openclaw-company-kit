"""Frontend integration tests: build verification, route completeness, panel registry, API registration."""

import os
import unittest

TESTS_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.join(TESTS_DIR, "..")
CONSOLE_VUE_DIR = os.path.join(ROOT_DIR, "frontend", "console-vue")


class TestFrontendBuild(unittest.TestCase):
    """Verify that the Vite build output is valid."""

    def test_npm_build_succeeds(self):
        """npm run build produces dist/index.html."""
        dist_dir = os.path.join(CONSOLE_VUE_DIR, "dist")
        if not os.path.isdir(dist_dir):
            self.skipTest("dist/ not found — run 'npm run build' first")
        self.assertTrue(
            os.path.isfile(os.path.join(dist_dir, "index.html")),
            "dist/index.html missing after build",
        )

    def test_dist_has_assets(self):
        """Build output includes an assets directory."""
        dist_dir = os.path.join(CONSOLE_VUE_DIR, "dist")
        if not os.path.isdir(dist_dir):
            self.skipTest("dist/ not found — run 'npm run build' first")
        assets_dir = os.path.join(dist_dir, "assets")
        self.assertTrue(os.path.isdir(assets_dir), "dist/assets/ directory missing")


class TestFrontendRoutes(unittest.TestCase):
    """Verify that router.js declares all required panel routes."""

    ROUTER_PATH = os.path.join(CONSOLE_VUE_DIR, "src", "router.js")

    EXPECTED_ROUTES = [
        "/setup",
        "/kanban",
        "/monitor",
        "/overview",
        "/officials",
        "/templates",
        "/skills",
        "/sessions",
    ]

    CORE_ROUTES_NO_PLACEHOLDER = [
        "/setup",
        "/kanban",
        "/monitor",
        "/overview",
        "/officials",
        "/templates",
        "/sessions",
    ]

    @classmethod
    def setUpClass(cls):
        with open(cls.ROUTER_PATH) as f:
            cls._content = f.read()

    def test_router_has_8_panel_routes(self):
        """router.js contains all 8 panel paths."""
        for route in self.EXPECTED_ROUTES:
            with self.subTest(route=route):
                self.assertIn(route, self._content, f"Missing route: {route}")

    def test_no_placeholder_in_core_routes(self):
        """Core panel routes are not wired to PlaceholderView."""
        for line in self._content.splitlines():
            for route in self.CORE_ROUTES_NO_PLACEHOLDER:
                if f'"{route}"' in line or f"'{route}'" in line:
                    self.assertNotIn(
                        "PlaceholderView",
                        line,
                        f"Route {route} still uses PlaceholderView",
                    )

    def test_root_redirects_to_setup(self):
        """The '/' path redirects to /setup."""
        self.assertIn('redirect: "/setup"', self._content)


class TestPanelRegistry(unittest.TestCase):
    """Verify the panel registry exports all 8 panels."""

    REGISTRY_PATH = os.path.join(CONSOLE_VUE_DIR, "src", "panels", "registry.js")

    PANEL_IDS = [
        "setup",
        "kanban",
        "monitor",
        "overview",
        "officials",
        "templates",
        "skills",
        "sessions",
    ]

    @classmethod
    def setUpClass(cls):
        with open(cls.REGISTRY_PATH) as f:
            cls._content = f.read()

    def test_registry_has_8_panels(self):
        """registry.js contains all 8 panel IDs."""
        for pid in self.PANEL_IDS:
            with self.subTest(panel=pid):
                self.assertIn(pid, self._content, f"Missing panel: {pid}")

    def test_panels_have_routes(self):
        """Each panel entry has a route field."""
        self.assertGreaterEqual(
            self._content.count("route:"),
            len(self.PANEL_IDS),
            "Some panels are missing the route field",
        )

    def test_panels_have_order(self):
        """Each panel entry has an order field."""
        self.assertGreaterEqual(
            self._content.count("order:"),
            len(self.PANEL_IDS),
            "Some panels are missing the order field",
        )


class TestAPIAuth(unittest.TestCase):
    """Verify that all expected API routes are registered in the control server."""

    CS_PATH = os.path.join(ROOT_DIR, "scripts", "control_server.py")

    EXPECTED_APIS = [
        "/api/kanban",
        "/api/kanban/move",
        "/api/monitor/services",
        "/api/monitor/metrics",
        "/api/monitor/reviews",
        "/api/officials",
        "/api/templates",
        "/api/sessions",
    ]

    @classmethod
    def setUpClass(cls):
        with open(cls.CS_PATH) as f:
            cls._content = f.read()

    def test_all_api_routes_registered(self):
        """All panel API endpoints are present in control_server.py."""
        for api in self.EXPECTED_APIS:
            with self.subTest(api=api):
                self.assertIn(api, self._content, f"Missing API route: {api}")

    def test_auth_middleware_present(self):
        """Server implements bearer token authentication."""
        self.assertIn("Bearer", self._content)
        self.assertIn("AUTH_TOKEN", self._content)


if __name__ == "__main__":
    unittest.main()
