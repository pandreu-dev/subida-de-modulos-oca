from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal


class AunnaPortalIframeExample(CustomerPortal):
    @http.route(["/my/iframe-example"], type="http", auth="user", website=True)
    def portal_iframe_example(self, **kwargs):
        values = self._prepare_portal_layout_values()
        return http.request.render(
            "aunna_portal_iframe_example.portal_iframe_example_page",
            values,
        )
