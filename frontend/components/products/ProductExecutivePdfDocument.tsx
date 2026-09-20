import {
  Document,
  Page,
  StyleSheet,
  Text,
  View,
} from "@react-pdf/renderer";

import {
  ProductExecutiveReportData,
  formatReportDate,
  formatReportMetricValue,
  formatReportOpportunityValue,
  formatReportStatus,
} from "@/lib/buildProductExecutiveReportData";

import {
  normalizePriority,
} from "@/lib/insightModel";
import { resolveInsightLayers } from "@/lib/insightLayers";


interface Props {
  data: ProductExecutiveReportData;
}


const styles = StyleSheet.create({
  page: {
    paddingTop: 48,
    paddingBottom: 56,
    paddingHorizontal: 48,
    fontFamily: "Helvetica",
    fontSize: 10,
    color: "#1f2937",
    lineHeight: 1.45,
  },
  headerBar: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 6,
    backgroundColor: "#111827",
  },
  footer: {
    position: "absolute",
    bottom: 24,
    left: 48,
    right: 48,
    borderTopWidth: 1,
    borderTopColor: "#e5e7eb",
    paddingTop: 8,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  footerText: {
    fontSize: 8,
    color: "#9ca3af",
  },
  label: {
    fontSize: 8,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    color: "#6b7280",
    marginBottom: 4,
  },
  title: {
    fontSize: 24,
    fontFamily: "Helvetica-Bold",
    color: "#111827",
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 11,
    color: "#4b5563",
    marginBottom: 16,
    maxWidth: 480,
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 20,
  },
  metaPill: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 999,
    paddingVertical: 4,
    paddingHorizontal: 10,
    fontSize: 9,
    color: "#374151",
  },
  section: {
    marginTop: 18,
    marginBottom: 8,
  },
  sectionTitle: {
    fontSize: 13,
    fontFamily: "Helvetica-Bold",
    color: "#111827",
    marginBottom: 8,
    paddingBottom: 4,
    borderBottomWidth: 1,
    borderBottomColor: "#e5e7eb",
  },
  paragraph: {
    fontSize: 10,
    color: "#374151",
    marginBottom: 8,
  },
  insightCard: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 6,
    padding: 10,
    marginBottom: 8,
  },
  insightCardHigh: {
    borderColor: "#fecaca",
    backgroundColor: "#fef2f2",
  },
  insightCardMedium: {
    borderColor: "#fde68a",
    backgroundColor: "#fffbeb",
  },
  insightMeta: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 4,
  },
  badge: {
    fontSize: 8,
    fontFamily: "Helvetica-Bold",
    textTransform: "uppercase",
    color: "#374151",
  },
  insightHeadline: {
    fontSize: 10,
    fontFamily: "Helvetica-Bold",
    color: "#111827",
    marginBottom: 3,
  },
  numberedItem: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 6,
  },
  numberedIndex: {
    width: 16,
    height: 16,
    borderRadius: 999,
    backgroundColor: "#111827",
    color: "#ffffff",
    fontSize: 8,
    textAlign: "center",
    paddingTop: 3,
    fontFamily: "Helvetica-Bold",
  },
  table: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 6,
    overflow: "hidden",
    marginTop: 6,
  },
  tableHeader: {
    flexDirection: "row",
    backgroundColor: "#f9fafb",
    borderBottomWidth: 1,
    borderBottomColor: "#e5e7eb",
  },
  tableRow: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: "#f3f4f6",
  },
  tableCell: {
    padding: 8,
    fontSize: 9,
    color: "#374151",
  },
  tableCellHeader: {
    padding: 8,
    fontSize: 8,
    fontFamily: "Helvetica-Bold",
    textTransform: "uppercase",
    color: "#6b7280",
  },
  colPriority: { width: "12%" },
  colCategory: { width: "16%" },
  colMain: { width: "34%" },
  colSecondary: { width: "18%" },
  colDetail: { width: "20%" },
  colMetric: { width: "55%" },
  colValue: { width: "45%" },
  colRank: { width: "8%" },
  colType: { width: "14%" },
  colOpp: { width: "34%" },
  colPotential: { width: "14%" },
  colSource: { width: "16%" },
  emptyState: {
    fontSize: 9,
    color: "#6b7280",
    fontStyle: "italic",
  },
});


export default function ProductExecutivePdfDocument({
  data,
}: Props) {

  const generatedLabel =
    formatReportDate(data.generatedAt);

  const updatedLabel =
    formatReportDate(data.updatedAt);


  return (
    <Document
      title={`${data.productName} — Executive Report`}
      author="InsightPilot"
      subject="Executive data product report"
    >

      <Page size="LETTER" style={styles.page}>

        <View style={styles.headerBar} fixed />

        <Text style={styles.label}>
          Executive Report
        </Text>

        <Text style={styles.title}>
          {data.productName}
        </Text>

        {data.description ? (

          <Text style={styles.subtitle}>
            {data.description}
          </Text>

        ) : null}


        {data.businessPurpose ? (

          <Text style={styles.paragraph}>
            <Text style={{ fontFamily: "Helvetica-Bold" }}>
              Business purpose:{" "}
            </Text>
            {data.businessPurpose}
          </Text>

        ) : null}


        <View style={styles.metaRow}>

          <Text style={styles.metaPill}>
            Version {data.version}
          </Text>

          <Text style={styles.metaPill}>
            {formatReportStatus(data.status)}
          </Text>

          <Text style={styles.metaPill}>
            Health: {data.health.label}
          </Text>

          <Text style={styles.metaPill}>
            {data.coverage}% field coverage
          </Text>

          <Text style={styles.metaPill}>
            Generated {generatedLabel}
          </Text>

        </View>


        {data.analyses.length > 0 && (

          <Text style={styles.paragraph}>
            <Text style={{ fontFamily: "Helvetica-Bold" }}>
              Analyses included:{" "}
            </Text>
            {data.analyses.join(", ")}
          </Text>

        )}


        {data.changeOverview && (

          <View style={styles.section}>

            <Text style={styles.sectionTitle}>
              Changes since prior version
            </Text>

            <Text style={styles.paragraph}>
              {data.changeOverview}
            </Text>

          </View>

        )}


        <View style={styles.section}>

          <Text style={styles.sectionTitle}>
            Executive summary
          </Text>

          <Text style={styles.label}>
            Facts
          </Text>

          <Text style={styles.paragraph}>
            {data.summary.what_we_found}
          </Text>


          <Text style={styles.label}>
            Interpretation
          </Text>

          {data.summary.what_matters.length === 0 ? (

            <Text style={styles.emptyState}>
              No prioritized insights were identified.
            </Text>

          ) : (

            data.summary.what_matters.map(
              (item, index) => {

                const priority =
                  normalizePriority(
                    item.priority
                  );

                return (
                  <View
                    key={`${item.headline}-${index}`}
                    style={[
                      styles.insightCard,
                      priority === "high"
                        ? styles.insightCardHigh
                        : priority === "medium"
                          ? styles.insightCardMedium
                          : undefined,
                    ]}
                  >

                    <View style={styles.insightMeta}>

                      <Text style={styles.badge}>
                        {priority} priority
                      </Text>

                      <Text style={styles.badge}>
                        {item.category}
                      </Text>

                    </View>

                    <Text style={styles.insightHeadline}>
                      {item.headline}
                    </Text>

                    {item.detail ? (

                      <Text style={styles.paragraph}>
                        {item.detail}
                      </Text>

                    ) : null}

                  </View>
                );

              }
            )

          )}


          <Text style={styles.label}>
            Recommendations
          </Text>

          {data.summary.what_to_do_next.length === 0 ? (

            <Text style={styles.emptyState}>
              No recommended actions were generated.
            </Text>

          ) : (

            data.summary.what_to_do_next.map(
              (action, index) => (

                <View
                  key={`${action}-${index}`}
                  style={styles.numberedItem}
                >

                  <Text style={styles.numberedIndex}>
                    {index + 1}
                  </Text>

                  <Text style={styles.paragraph}>
                    {action}
                  </Text>

                </View>

              )
            )

          )}

        </View>


        <View style={styles.footer} fixed>

          <Text style={styles.footerText}>
            {data.productName} · v{data.version}
          </Text>

          <Text style={styles.footerText}>
            InsightPilot · {generatedLabel}
          </Text>

        </View>

      </Page>


      <Page size="LETTER" style={styles.page}>

        <View style={styles.headerBar} fixed />

        <View style={styles.section}>

          <Text style={styles.sectionTitle}>
            Key metrics
          </Text>

          {data.kpis.length === 0 ? (

            <Text style={styles.emptyState}>
              No headline metrics were available for this version.
            </Text>

          ) : (

            <View style={styles.table}>

              <View style={styles.tableHeader}>

                <Text style={[styles.tableCellHeader, styles.colMetric]}>
                  Metric
                </Text>

                <Text style={[styles.tableCellHeader, styles.colValue]}>
                  Value
                </Text>

              </View>


              {data.kpis.map((metric) => (

                <View
                  key={metric.id}
                  style={styles.tableRow}
                >

                  <Text style={[styles.tableCell, styles.colMetric]}>
                    {metric.name}
                  </Text>

                  <Text style={[styles.tableCell, styles.colValue]}>
                    {formatReportMetricValue(metric)}
                  </Text>

                </View>

              ))}

            </View>

          )}

        </View>


        <View style={styles.section}>

          <Text style={styles.sectionTitle}>
            Top opportunities
          </Text>

          {data.opportunities.length === 0 ? (

            <Text style={styles.emptyState}>
              No ranked opportunities were identified.
            </Text>

          ) : (

            <View style={styles.table}>

              <View style={styles.tableHeader}>

                <Text style={[styles.tableCellHeader, styles.colRank]}>
                  #
                </Text>

                <Text style={[styles.tableCellHeader, styles.colType]}>
                  Type
                </Text>

                <Text style={[styles.tableCellHeader, styles.colOpp]}>
                  Opportunity
                </Text>

                <Text style={[styles.tableCellHeader, styles.colPriority]}>
                  Priority
                </Text>

                <Text style={[styles.tableCellHeader, styles.colPotential]}>
                  Potential
                </Text>

                <Text style={[styles.tableCellHeader, styles.colSource]}>
                  Source
                </Text>

              </View>


              {data.opportunities.map(
                (opportunity, index) => (

                  <View
                    key={opportunity.id}
                    style={styles.tableRow}
                  >

                    <Text style={[styles.tableCell, styles.colRank]}>
                      {index + 1}
                    </Text>

                    <Text style={[styles.tableCell, styles.colType]}>
                      {opportunity.type}
                    </Text>

                    <Text style={[styles.tableCell, styles.colOpp]}>
                      {opportunity.label}
                    </Text>

                    <Text style={[styles.tableCell, styles.colPriority]}>
                      {opportunity.priority}
                    </Text>

                    <Text style={[styles.tableCell, styles.colPotential]}>
                      {formatReportOpportunityValue(opportunity)}
                    </Text>

                    <Text style={[styles.tableCell, styles.colSource]}>
                      {opportunity.source}
                    </Text>

                  </View>

                )
              )}

            </View>

          )}

        </View>


        <View style={styles.section}>

          <Text style={styles.sectionTitle}>
            Priority insights
          </Text>

          {data.insights.length === 0 ? (

            <Text style={styles.emptyState}>
              No insights were generated for this version.
            </Text>

          ) : (

            <View style={styles.table}>

              <View style={styles.tableHeader}>

                <Text style={[styles.tableCellHeader, styles.colPriority]}>
                  Priority
                </Text>

                <Text style={[styles.tableCellHeader, styles.colCategory]}>
                  Category
                </Text>

                <Text style={[styles.tableCellHeader, styles.colMain]}>
                  Fact
                </Text>

                <Text style={[styles.tableCellHeader, styles.colSecondary]}>
                  Interpretation
                </Text>

                <Text style={[styles.tableCellHeader, styles.colDetail]}>
                  Recommendation
                </Text>

              </View>


              {data.insights.map((insight) => {
                const layers = resolveInsightLayers(insight);

                return (

                <View
                  key={insight.id}
                  style={styles.tableRow}
                >

                  <Text style={[styles.tableCell, styles.colPriority]}>
                    {normalizePriority(insight.priority)}
                  </Text>

                  <Text style={[styles.tableCell, styles.colCategory]}>
                    {insight.category ?? "—"}
                  </Text>

                  <Text style={[styles.tableCell, styles.colMain]}>
                    {layers.fact || "—"}
                  </Text>

                  <Text style={[styles.tableCell, styles.colSecondary]}>
                    {layers.interpretation || "—"}
                  </Text>

                  <Text style={[styles.tableCell, styles.colDetail]}>
                    {layers.recommendation || "—"}
                  </Text>

                </View>

                );
              })}

            </View>

          )}

        </View>


        <Text style={[styles.paragraph, { marginTop: 16 }]}>
          <Text style={{ fontFamily: "Helvetica-Bold" }}>
            Product health:{" "}
          </Text>
          {data.health.summary}
        </Text>


        {data.health.reasons.length > 0 && (

          data.health.reasons.map(
            (reason, index) => (

              <Text
                key={`${reason}-${index}`}
                style={styles.paragraph}
              >
                • {reason}
              </Text>

            )
          )

        )}


        <View style={styles.footer} fixed>

          <Text style={styles.footerText}>
            Data current as of {updatedLabel}
          </Text>

          <Text style={styles.footerText}>
            InsightPilot · Page 2
          </Text>

        </View>

      </Page>

    </Document>

  );

}
