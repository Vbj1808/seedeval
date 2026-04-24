import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ScoreBadge } from "@/components/ScoreBadge";
import { CheckResult } from "@/lib/types";

export function CheckResultCard({ check }: { check: CheckResult }) {
  return (
    <Card className="border-border bg-card">
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="text-sm font-medium capitalize">{check.check_name}</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            {new Date(check.created_at).toLocaleTimeString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ScoreBadge score={check.score} />
          <Badge variant={check.passed ? "secondary" : "destructive"}>
            {check.passed ? "Pass" : "Fail"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <Separator />
        <details className="group">
          <summary className="cursor-pointer list-none text-xs font-medium text-muted-foreground group-open:text-foreground">
            Details
          </summary>
          <pre className="mt-3 overflow-x-auto rounded-md bg-background p-3 text-xs leading-5 text-muted-foreground">
            {JSON.stringify(check.details, null, 2)}
          </pre>
        </details>
      </CardContent>
    </Card>
  );
}
