import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
  } from "@/components/ui/card";
  
  import { DatasetProfile } from "@/types/report";
  
  interface Props {
    profile: DatasetProfile;
  }
  
  export default function ColumnExplorer({
    profile,
  }: Props) {
  
    const columns = profile.columns?.names || [];
  
    return (
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>
            Column Explorer
          </CardTitle>
        </CardHeader>
  
        <CardContent>
  
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
  
            {columns.map((column) => (
              <div
                key={column}
                className="rounded-lg border bg-muted/20 p-3 transition-colors hover:bg-muted/40"
              >
                <div className="font-medium">
                  {column}
                </div>
  
                <div className="mt-1 text-xs text-muted-foreground">
                  Available for analysis
                </div>
  
              </div>
            ))}
  
          </div>
  
        </CardContent>
      </Card>
    );
  }