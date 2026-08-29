/**
 * "You already own 61% of this fund" — at the moment of choosing, not after.
 *
 * The number that decides whether adding a fund does anything. Two large-cap
 * funds and a third is usually the same thirty companies a third time, and
 * every other figure on the page — the rank, the cost, the base rate — will say
 * the third fund is good.
 *
 * **It renders `n/a`, never `0%`, when unmeasured.** §14. 0% reads as perfectly
 * diversified, which is the opposite of "we could not tell", and it is the more
 * attractive of the two readings — so a silent zero encourages the purchase it
 * should have questioned.
 */
import { useQuery } from '@tanstack/react-query'
import { fetchAlreadyOwn } from '@/lib/portfolio-api'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'

export function AlreadyOwn({ schemeCode }: { schemeCode: string }) {
  const { data, isPending, isError } = useQuery({
    queryKey: ['already-own', schemeCode],
    queryFn: () => fetchAlreadyOwn(schemeCode),
    retry: false,
  })

  if (isPending) {
    return (
      <Panel title="How much of this you already own">
        <Skeleton className="h-5 w-48" />
      </Panel>
    )
  }
  if (isError || !data) {
    return (
      <Panel title="How much of this you already own">
        <p className="text-sm text-muted-foreground">
          We could not check this against your portfolio just now.
        </p>
      </Panel>
    )
  }

  const measured = data.share_pct !== null

  return (
    <Panel title="How much of this you already own">
      <p className="num text-2xl font-semibold">
        {measured ? `${data.share_pct!.toFixed(0)}%` : 'n/a'}
      </p>
      <p className="mt-1 text-sm text-muted-foreground">{data.summary}</p>
      {measured && data.through.length > 0 && (
        <ul className="mt-3 divide-y text-sm">
          {data.through.map(([name, share]) => (
            <li key={name} className="flex items-baseline justify-between gap-3 py-1.5">
              <span className="truncate">{name}</span>
              <span className="num shrink-0 text-muted-foreground">
                {share.toFixed(1)}%
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
