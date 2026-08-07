import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
  } from "@/components/ui/card";
  
  import { ExecutiveBrief } from "@/types/report";
  
  interface Props {
    brief: ExecutiveBrief | null;
    loading: boolean;
  }
  
  export default function ExecutiveBriefCard({
    brief,
    loading,
  }: Props) {
  
    return (
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>
            Executive Brief
          </CardTitle>
        </CardHeader>
  
        <CardContent>
  
          {loading && (
            <p>
              Generating executive briefing...
            </p>
          )}
  
          {!loading && brief && (
            <div className="space-y-6">
  
              <div>
                <h3 className="font-semibold">
                  Overview
                </h3>
  
                <p className="mt-2 text-sm text-muted-foreground">
                  {brief.overview}
                </p>
              </div>
  
  
              {brief.key_findings.length > 0 && (
                <div>
                  <h3 className="font-semibold">
                    Key Findings
                  </h3>
  
                  <ul className="mt-2 list-disc pl-5 text-sm">
                    {brief.key_findings.map((item, index) => (
                      <li key={index}>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
  
  
              {brief.risks.length > 0 && (
                <div>
                  <h3 className="font-semibold">
                    Risks
                  </h3>
  
                  <ul className="mt-2 list-disc pl-5 text-sm">
                    {brief.risks.map((item, index) => (
                      <li key={index}>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
  
  
              {brief.opportunities.length > 0 && (
                <div>
                  <h3 className="font-semibold">
                    Opportunities
                  </h3>
  
                  <ul className="mt-2 space-y-2 text-sm">
                    {brief.opportunities.map((item) => (
                      <li key={item.id}>
                        <span className="font-medium">
                          {item.title}
                        </span>
  
                        {item.category && (
                          <span className="ml-2 text-muted-foreground">
                            ({item.category})
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
  
  
              {brief.next_steps.length > 0 && (
                <div>
                  <h3 className="font-semibold">
                    Next Steps
                  </h3>
  
                  <ul className="mt-2 list-disc pl-5 text-sm">
                    {brief.next_steps.map((item, index) => (
                      <li key={index}>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
  
            </div>
          )}
  
        </CardContent>
      </Card>
    );
  }