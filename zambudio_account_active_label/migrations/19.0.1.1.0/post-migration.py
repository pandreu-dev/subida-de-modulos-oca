from odoo import SUPERUSER_ID, api

from odoo.addons.zambudio_account_active_label import _fix_active_label


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _fix_active_label(env)
