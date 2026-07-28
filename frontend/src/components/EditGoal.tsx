import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatInr } from '@/lib/format'

/**
 * Changing a goal, with the consequence visible before it is saved.
 *
 * The affordability line on the goals page says a target or date has to move,
 * and that pushing a date out is usually cheaper than cutting a target. That is
 * a claim the user should be able to check rather than take on trust, so the
 * new monthly figure is computed live from whatever is currently in the form.
 */

type Goal = {
  id: string
  goal_name: string
  target_amount: number
  current_savings: number
  target_date: string
  years: number
  required_monthly_sip: number | null
  inflation_rate: number | null
}

function yearsBetween(iso: string): number {
  const years = (new Date(iso).getTime() - Date.now()) / (365.25 * 24 * 60 * 60 * 1000)
  return Math.max(0.5, Math.round(years * 10) / 10)
}

export function EditGoal({ goal, onClose }: { goal: Goal; onClose: () => void }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState(goal.goal_name)
  const [target, setTarget] = useState(String(goal.target_amount))
  const [saved, setSaved] = useState(String(goal.current_savings))
  const [date, setDate] = useState(goal.target_date.slice(0, 10))
  const [confirmDelete, setConfirmDelete] = useState(false)

  const years = yearsBetween(date)
  const targetNumber = Number(target) || 0
  const savedNumber = Number(saved) || 0

  // The same calculator the goal itself was priced with, so the preview and the
  // saved figure cannot disagree.
  const { data: preview, isError: previewFailed } = useQuery({
    queryKey: ['sip-preview', targetNumber, savedNumber, years, goal.inflation_rate],
    queryFn: async () =>
      (
        await api.post('/api/v1/advisor/calculate-sip', {
          target_amount: targetNumber,
          years,
          current_savings: savedNumber,
          inflation_rate: goal.inflation_rate ?? 0.06,
        })
      ).data as { required_monthly_sip: number },
    enabled: targetNumber > 0 && years > 0,
    retry: false,
  })

  /** Everything that reads this goal, or reads across all of them. */
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['goal', goal.id] })
    queryClient.invalidateQueries({ queryKey: ['goals'] })
    queryClient.invalidateQueries({ queryKey: ['goal-commitment'] })
    queryClient.invalidateQueries({ queryKey: ['goal-recommendations', goal.id] })
  }

  const save = useMutation({
    mutationFn: async () =>
      (
        await api.patch(`/api/v1/goals/${goal.id}`, {
          goal_name: name,
          target_amount: targetNumber,
          current_savings: savedNumber,
          target_date: date,
          years,
        })
      ).data,
    onSuccess: () => {
      invalidate()
      onClose()
    },
  })

  const remove = useMutation({
    mutationFn: () => api.delete(`/api/v1/goals/${goal.id}`),
    onSuccess: () => {
      // Dropped, not invalidated. Invalidating a deleted goal's query refetches
      // it, and the 404 that comes back renders "couldn't load this goal" over
      // the top of a page that is on its way out.
      queryClient.removeQueries({ queryKey: ['goal', goal.id] })
      queryClient.removeQueries({ queryKey: ['goal-recommendations', goal.id] })
      queryClient.invalidateQueries({ queryKey: ['goals'] })
      queryClient.invalidateQueries({ queryKey: ['goal-commitment'] })
      navigate('/goals', { replace: true })
    },
  })

  const current = goal.required_monthly_sip ?? 0
  // Never falls back to the current figure. Doing that made a failed preview
  // read as "nothing changes", which is the one thing it must not say.
  const next = preview?.required_monthly_sip ?? null
  const change = next === null ? null : next - current

  return (
    <section className="flex flex-col gap-6 border-y py-6">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <h2 className="text-sm font-medium">Change this goal</h2>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
      </div>

      <form
        className="flex max-w-lg flex-col gap-5"
        onSubmit={(e) => {
          e.preventDefault()
          save.mutate()
        }}
      >
        <div className="flex flex-col gap-2">
          <Label htmlFor="goal-name">Name</Label>
          <Input id="goal-name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="goal-target">Target amount</Label>
          <Input
            id="goal-target"
            type="number"
            min={1}
            inputMode="numeric"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            In today&rsquo;s money. We inflate it to what it will cost by the date
            below.
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="goal-date">Date you need it</Label>
          <Input
            id="goal-date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            <span className="tnum">{years}</span> years away. Pushing this out is
            usually the cheapest way to make a goal fit, because the extra years
            compound.
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="goal-saved">Already saved toward it</Label>
          <Input
            id="goal-saved"
            type="number"
            min={0}
            inputMode="numeric"
            value={saved}
            onChange={(e) => setSaved(e.target.value)}
          />
        </div>

        {/* The consequence, before it is committed. */}
        <div className="flex flex-col gap-1 border-l-2 border-primary py-1 pl-3">
          {next === null ? (
            <p className="text-sm text-muted-foreground">
              {previewFailed
                ? 'Could not work out the new monthly figure. Check the date is in the future, and it will appear here.'
                : 'Working out the new monthly figure…'}
            </p>
          ) : (
            <p className="text-sm">
              <span className="num font-medium">{formatInr(next)}</span> a month
              {change !== null && Math.abs(change) >= 1 && (
                <>
                  {' '}
                  &mdash;{' '}
                  <span className={`num ${change < 0 ? 'text-gain' : 'text-loss'}`}>
                    {change < 0 ? '−' : '+'}
                    {formatInr(Math.abs(change))}
                  </span>{' '}
                  against what it asks for now
                </>
              )}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            Recomputed from the form as you type, with the same calculator that
            priced the goal.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-1">
          <Button type="submit" disabled={save.isPending || targetNumber <= 0}>
            {save.isPending ? 'Saving' : 'Save changes'}
          </Button>
          {save.isError && (
            <span className="text-sm text-loss">
              That did not save. Check the target is above zero and the date is in
              the future.
            </span>
          )}
        </div>
      </form>

      <div className="flex flex-wrap items-center gap-3 border-t pt-5">
        {confirmDelete ? (
          <>
            <span className="text-sm">
              Delete &ldquo;{goal.goal_name}&rdquo;? This cannot be undone.
            </span>
            <Button
              variant="destructive"
              size="sm"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              {remove.isPending ? 'Deleting' : 'Delete it'}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>
              Keep it
            </Button>
          </>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)}>
            Delete this goal
          </Button>
        )}
      </div>
    </section>
  )
}
