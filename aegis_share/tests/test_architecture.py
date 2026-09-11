from django.test import SimpleTestCase
from django.urls import URLPattern, URLResolver, get_resolver


LEGACY_PUBLIC_API_ROUTES = {
    "api/v1/files/",
    "api/v1/files/<int:file_id>/",
    "api/v1/files/<int:file_id>/download/",
}


def _collect_routes(patterns, prefix=""):
    routes = set()
    for entry in patterns:
        route = f"{prefix}{entry.pattern}"
        if isinstance(entry, URLResolver):
            routes.update(_collect_routes(entry.url_patterns, route))
        elif isinstance(entry, URLPattern):
            routes.add(route)
    return routes


class PublicApiArchitectureTests(SimpleTestCase):
    def test_no_new_public_api_routes_are_introduced(self):
        routes = _collect_routes(get_resolver().url_patterns)
        api_routes = {route for route in routes if route.startswith("api/")}

        self.assertSetEqual(api_routes, LEGACY_PUBLIC_API_ROUTES)
