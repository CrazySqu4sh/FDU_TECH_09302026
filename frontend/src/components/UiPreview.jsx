import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

// Unlinked page (?page=ui): shows shadcn/ui pieces in Aparece's theme, to check v0 components will match.
export default function UiPreview() {
  return (
    <div className="v0 mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wider text-accent">Design system check</p>
        <h1 className="font-display text-4xl font-bold">v0 / shadcn components in Aparece’s theme</h1>
        <p className="mt-2 text-muted-foreground">If this page looks right, components pasted from v0 will match the app.</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button>Scan my business</Button>
        <Button variant="secondary">See plans</Button>
        <Button variant="outline">Sign in</Button>
        <Button className="bg-accent text-accent-foreground hover:bg-accent/90">Start free trial</Button>
        <Button variant="destructive">Delete</Button>
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge>Estimate</Badge>
        <Badge variant="secondary">Medium impact</Badge>
        <Badge className="bg-success text-success-foreground">Measured</Badge>
        <Badge variant="destructive">High impact</Badge>
        <Badge variant="outline">EN</Badge>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {[['68%', 'Estimated visibility'], ['84/100', 'Website readiness'], ['16', 'Customer questions']].map(([v, l]) => (
          <Card key={l}>
            <CardHeader><CardDescription>{l}</CardDescription><CardTitle className="font-display text-3xl">{v}</CardTitle></CardHeader>
            <CardContent className="text-sm text-muted-foreground">shadcn Card with Aparece colors</CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
