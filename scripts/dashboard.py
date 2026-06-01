class DashboardService:
    def __init__(self, inventory_manager):
        self.inventory_manager = inventory_manager

    def get_low_stock(self):
        return self.inventory_manager.get_low_stock_items()

    def get_summary(self):
        items = self.inventory_manager.get_all_items()
        low_stock_items = self.inventory_manager.get_low_stock_items()

        status_ok = 0
        status_below = 0
        status_no_minimum = 0

        for item in items:
            quantity = item.get('quantity', 0)
            minimum = item.get('minimum_quantity', 0)

            if minimum == 0:
                status_no_minimum += 1
            elif quantity <= minimum:
                status_below += 1
            else:
                status_ok += 1

        total_status = max(
            status_ok + status_below + status_no_minimum,
            1
        )

        ok_percent = round((status_ok / total_status) * 100, 1)
        below_percent = round((status_below / total_status) * 100, 1)
        no_minimum_percent = round((status_no_minimum / total_status) * 100, 1)

        return {
            'items': items,
            'low_stock': low_stock_items,
            'total_items': len(items),
            'total_stock': sum(item['quantity'] for item in items),

            'status_ok': status_ok,
            'status_below': status_below,
            'status_no_minimum': status_no_minimum,

            'ok_percent': ok_percent,
            'below_percent': below_percent,
            'no_minimum_percent': no_minimum_percent,
        }