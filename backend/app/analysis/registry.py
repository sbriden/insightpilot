from .modules.customer_concentration import (
    CustomerConcentrationModule
)

from .modules.profitability import (
    ProfitabilityModule
)

from .modules.revenue_trends import (
    RevenueTrendsModule
)

from .modules.product_performance import (
    ProductPerformanceModule
)

from .modules.customer_performance import (
    CustomerPerformanceModule
)

from .modules.customer_product import (
    CustomerProductModule
)

from .modules.cross_sell import CrossSellModule

from .modules.customer_growth import CustomerGrowthModule

from .modules.profit_improvement import (
    ProfitImprovementModule,
)

from .modules.opportunity_summary import (
    OpportunitySummaryModule,
)


MODULES = [

    CustomerConcentrationModule(),

    ProfitabilityModule(),

    RevenueTrendsModule(),

    ProductPerformanceModule(),

    CustomerPerformanceModule(),

    CustomerProductModule(),

    CrossSellModule(),

    CustomerGrowthModule(),

    ProfitImprovementModule(),

    OpportunitySummaryModule(),

]