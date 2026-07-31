import { useEffect, useState } from 'react'
import { Panel } from '@/components/ui/panel'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Metric, MetricRow } from '@/components/ui/metric'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr } from '@/lib/format'
import { fetchProfile, saveProfile, type Profile as ProfileT } from '@/lib/api'

type FieldKey =
  | 'annual_income'
  | 'basic_salary'
  | 'existing_80c'
  | 'existing_80d'
  | 'other_deductions'
  | 'years_to_goal'

const FIELDS: { key: FieldKey; label: string; hint: string }[] = [
  {
    key: 'annual_income',
    label: 'Annual income',
    hint: 'Gross, before any deduction. This is what decides which tax regime costs you less.',
  },
  {
    key: 'basic_salary',
    label: 'Basic salary',
    hint: 'Basic, not CTC. The employer NPS deduction is capped at a share of basic, and guessing it from CTC would be a made-up number.',
  },
  {
    key: 'existing_80c',
    label: '80C already claimed',
    hint: 'EPF, PPF, ELSS, life insurance, home loan principal. Only counts in the old regime.',
  },
  {
    key: 'existing_80d',
    label: '80D already claimed',
    hint: 'Health insurance premiums. Only counts in the old regime.',
  },
  {
    key: 'other_deductions',
    label: 'Other deductions',
    hint: 'HRA, home loan interest, 80E, 80G. Without these the old regime looks worse than it is for anyone paying rent or a mortgage.',
  },
  {
    key: 'years_to_goal',
    label: 'Years until you need the money',
    hint: 'Every lifetime figure in the app is measured over this.',
  },
]

export function Profile() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['profile'], queryFn: fetchProfile })
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [salaried, setSalaried] = useState(true)
  const [regime, setRegime] = useState<'new' | 'old'>('new')

  useEffect(() => {
    if (!data) return
    setSalaried(data.is_salaried)
    setRegime(data.current_tax_regime === 'old' ? 'old' : 'new')
    setDraft(
      Object.fromEntries(
        FIELDS.map((f) => [f.key, data[f.key] === null ? '' : String(data[f.key])]),
      ),
    )
  }, [data])

  const save = useMutation({
    mutationFn: (patch: Partial<ProfileT>) => saveProfile(patch),
    onSuccess: (fresh) => queryClient.setQueryData(['profile'], fresh),
  })

  if (isLoading) return <Skeleton className="h-96 w-full" />

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const patch: Record<string, unknown> = {
      is_salaried: salaried,
      current_tax_regime: regime,
    }
    for (const f of FIELDS) {
      const raw = draft[f.key]
      if (raw !== undefined && raw !== '') patch[f.key] = Number(raw)
    }
    save.mutate(patch as Partial<ProfileT>)
  }

  const tax = data?.tax

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Your situation</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          The tax regime you are in is the single largest thing we can measure for
          you, and it needs an income to work out. Nothing here is guessed: leave a
          field blank and we simply do not use it.
        </p>
      </header>

      {/* The answer beside the inputs that produce it, so changing a number and
          seeing what it does is one glance rather than a scroll. */}
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,32rem)_minmax(0,1fr)]">
      {tax && (
        <Panel
          title={`The ${tax.recommended === 'new' ? 'new' : 'old'} regime is cheaper for you`}
        >
          <MetricRow className="sm:grid-cols-3 lg:grid-cols-3 sm:[&>*:nth-child(3n+1)]:pl-0 sm:[&>*:nth-child(3n)]:border-r-0">
            <Metric
              label="New regime"
              value={formatInr(tax.new_regime_tax)}
              valueClassName={tax.recommended === 'new' ? 'text-gain' : undefined}
              size="sm"
            />
            <Metric
              label="Old regime"
              value={formatInr(tax.old_regime_tax)}
              valueClassName={tax.recommended === 'old' ? 'text-gain' : undefined}
              size="sm"
            />
            <Metric
              label="You save"
              value={formatInr(tax.saving)}
              hint="A year, every year, for declaring the right one."
              size="sm"
            />
          </MetricRow>
          <p className="max-w-3xl text-sm text-muted-foreground">{tax.rationale}</p>
        </Panel>
      )}

      {/* The form stays a reading column. A settings form is worked through in
          order, so full width would make every label a long saccade from its
          field. */}
      <Panel title="Your numbers" className="xl:order-first">
      <form onSubmit={submit} className="flex max-w-lg flex-col gap-5">
        <div className="flex flex-col gap-2">
          <Label htmlFor="salaried">Income type</Label>
          <select
            id="salaried"
            className="h-9 rounded-md border bg-transparent px-2 text-sm"
            value={salaried ? 'salaried' : 'other'}
            onChange={(e) => setSalaried(e.target.value === 'salaried')}
          >
            <option value="salaried">Salaried</option>
            <option value="other">Business or professional</option>
          </select>
          <p className="text-xs text-muted-foreground">
            Salaried gets a standard deduction, which changes the comparison.
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="regime">Regime you are in today</Label>
          <select
            id="regime"
            className="h-9 rounded-md border bg-transparent px-2 text-sm"
            value={regime}
            onChange={(e) => setRegime(e.target.value === 'old' ? 'old' : 'new')}
          >
            <option value="new">New regime</option>
            <option value="old">Old regime</option>
          </select>
          <p className="text-xs text-muted-foreground">
            Which one you are actually in, not the one you should be in. New is the
            default since FY2023-24, so if you never filed a declaration with your
            employer, you are in it. This decides whether switching is worth money to
            you or whether you already have the saving.
          </p>
        </div>

        {FIELDS.map((f) => (
          <div key={f.key} className="flex flex-col gap-2">
            <Label htmlFor={f.key}>{f.label}</Label>
            <Input
              id={f.key}
              type="number"
              min={0}
              inputMode="numeric"
              value={draft[f.key] ?? ''}
              onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
            />
            <p className="text-xs text-muted-foreground">{f.hint}</p>
          </div>
        ))}

        <div className="flex items-center gap-3 pt-1">
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? 'Saving' : 'Save'}
          </Button>
          {save.isSuccess && !save.isPending && (
            <span className="text-sm text-muted-foreground">Saved.</span>
          )}
          {save.isError && (
            <span className="text-sm text-loss">
              That did not save. Check the figures are not negative and try again.
            </span>
          )}
        </div>
      </form>
      </Panel>
      </div>
    </div>
  )
}
