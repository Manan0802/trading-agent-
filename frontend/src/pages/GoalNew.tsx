import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type GoalForm = {
  goal_type: string
  goal_name: string
  target_amount: number
  target_date: string
  years: number
  risk_profile: string
}

const GOAL_TYPES = [
  { value: 'retirement', label: 'Retirement' },
  { value: 'home', label: 'House or major purchase' },
  { value: 'education', label: "Child's education" },
  { value: 'general', label: 'General investing' },
]

const RISK_PROFILES = [
  { value: 'conservative', label: 'Conservative' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'aggressive', label: 'Aggressive' },
]

export function GoalNew() {
  const navigate = useNavigate()
  const [form, setForm] = useState<GoalForm>({
    goal_type: 'home',
    goal_name: '',
    target_amount: 2000000,
    target_date: '2031-01-01',
    years: 5,
    risk_profile: 'moderate',
  })

  const set = <K extends keyof GoalForm>(key: K, value: GoalForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const createGoal = useMutation({
    mutationFn: async () => {
      const { data } = await api.post('/api/v1/goals', form)
      return data
    },
    onSuccess: (data) => navigate(`/goals/${data.id}`),
  })

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1.5">
        <h1 className="font-heading text-3xl font-semibold leading-[1.1] tracking-[-0.02em] sm:text-4xl">New goal</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Tell us what you are saving for and when you need it. We work out the monthly
          SIP that gets you there, the split between equity, debt and gold, and which
          Direct Growth funds to buy.
        </p>
      </header>

      <form
        className="flex max-w-lg flex-col gap-5"
        onSubmit={(e) => {
          e.preventDefault()
          createGoal.mutate()
        }}
      >
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="goal_name">Goal name</Label>
          <Input
            id="goal_name"
            placeholder="Dream house"
            required
            value={form.goal_name}
            onChange={(e) => set('goal_name', e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="goal_type">Goal type</Label>
          <Select
            value={form.goal_type}
            onValueChange={(v) => set('goal_type', v as string)}
          >
            <SelectTrigger id="goal_type" className="w-full">
              {/* Without a formatter the trigger shows the stored value, so the
                  field reads "home" instead of what the user picked. */}
              <SelectValue placeholder="Select a goal type">
                {(value) =>
                  GOAL_TYPES.find((t) => t.value === value)?.label ?? value
                }
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {GOAL_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="target_amount">Target amount (₹)</Label>
            <Input
              id="target_amount"
              className="num"
              type="number"
              min={1}
              required
              value={form.target_amount}
              onChange={(e) => set('target_amount', Number(e.target.value))}
            />
            <p className="text-xs text-muted-foreground">
              What you want to have by the end.
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="years">Years to goal</Label>
            <Input
              id="years"
              className="num"
              type="number"
              min={1}
              step={0.5}
              required
              value={form.years}
              onChange={(e) => set('years', Number(e.target.value))}
            />
            <p className="text-xs text-muted-foreground">
              How long the money has to compound.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="target_date">Target date</Label>
          <Input
            id="target_date"
            className="num"
            type="date"
            required
            value={form.target_date}
            onChange={(e) => set('target_date', e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="risk_profile">Risk profile</Label>
          <Select
            value={form.risk_profile}
            onValueChange={(v) => set('risk_profile', v as string)}
          >
            <SelectTrigger id="risk_profile" className="w-full">
              <SelectValue placeholder="Select a risk profile">
                {(value) =>
                  RISK_PROFILES.find((r) => r.value === value)?.label ?? value
                }
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {RISK_PROFILES.map((r) => (
                <SelectItem key={r.value} value={r.value}>
                  {r.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            This sets how much of the plan sits in equity, which is the part that can
            fall in any given year.
          </p>
        </div>

        {createGoal.isError && (
          <p className="text-sm text-destructive">
            We could not create this goal. Check the fields above and try again; if it
            keeps failing, the server is not responding.
          </p>
        )}

        <div>
          <Button type="submit" size="lg" disabled={createGoal.isPending}>
            {createGoal.isPending ? 'Working out your plan…' : 'Create goal'}
          </Button>
        </div>
      </form>
    </div>
  )
}
