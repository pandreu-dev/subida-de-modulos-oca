from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPurchaseOrderType(TransactionCase):
    def test_create_purchase_order_type(self):
        order_type = self.env["aunna.purchase.order.type"].create({"name": "Material"})

        self.assertEqual(order_type.name, "Material")
