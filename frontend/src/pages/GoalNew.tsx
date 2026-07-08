import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
  { value: 'home', label: 'House / Major Purchase' },
  { value: 'education', label: "Child's Education" },
  { value: 'general', label: 'General Investing' },
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
    <div className="mx-auto max-w-lg px-4 py-10">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Create a financial goal</CardTitle>
          <CardDescription>
            Tell us what you're saving for — we'll work out the projected SIP and allocation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault()
              createGoal.mutate()
            }}
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="goal_name">Goal name</Label>
              <Input
                id="goal_name"
                placeholder="e.g. Dream House"
                required
                value={form.goal_name}
                onChange={(e) => set('goal_name', e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="goal_type">Goal type</Label>
              <Select value={form.goal_type} onValueChange={(v) => set('goal_type', v as string)}>
                <SelectTrigger id="goal_type" className="w-full">
                  <SelectValue placeholder="Select a goal type" />
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
                  type="number"
                  min={1}
                  required
                  value={form.target_amount}
                  onChange={(e) => set('target_amount', Number(e.target.value))}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="years">Years to goal</Label>
                <Input
                  id="years"
                  type="number"
                  min={1}
                  step={0.5}
                  required
                  value={form.years}
                  onChange={(e) => set('years', Number(e.target.value))}
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="target_date">Target date</Label>
              <Input
                id="target_date"
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
                  <SelectValue placeholder="Select a risk profile" />
                </SelectTrigger>
                <SelectContent>
                  {RISK_PROFILES.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {createGoal.isError && (
              <p className="text-sm text-destructive">
                Something went wrong creating your goal. Please try again.
              </p>
            )}

            <Button type="submit" size="lg" disabled={createGoal.isPending}>
              {createGoal.isPending ? 'Creating your plan…' : 'Create goal'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
