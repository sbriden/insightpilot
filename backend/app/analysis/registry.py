from .modules.customer_concentration import (
    CustomerConcentrationModule
)

from .modules.profitability import (
    ProfitabilityModule
)

from .modules.revenue_trends import (
    RevenueTrendsModule
)


MODULES = [

    CustomerConcentrationModule(),

    ProfitabilityModule(),

    RevenueTrendsModule(),

]