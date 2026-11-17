def post_init_hook(env):
    env["product.category"]._mark_default_project_delivery_excluded_categories()
    env["stock.move"]._apply_project_delivery_rule_to_pending_moves()
