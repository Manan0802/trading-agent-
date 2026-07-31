import { useQuery } from '@tanstack/react-query'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchAnnouncements } from '@/lib/portfolio-api'

/**
 * What changed about the companies you own — not a news feed.
 *
 * The distinction is the whole design. Retail investors who watch more, trade
 * more, and turnover and tax are two of the few things this app has measured as
 * decisive. So there is no ticker, no market commentary and no prices here:
 * every row is a filing about something already in the portfolio, and the
 * closing line says out loud that none of it is a reason to trade.
 */

function daysAgo(iso: string): string {
  const days = Math.round((Date.now() - new Date(iso).getTime()) / 86_400_000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days} days ago`
  const months = Math.round(days / 30)
  return months === 1 ? 'a month ago' : `${months} months ago`
}

/** NSE writes categories at legal length. The row has a column, not a page. */
function shortCategory(category: string): string {
  return category.split('(')[0].split(' or the ')[0].trim()
}

export function Announcements() {
  const { data, isLoading } = useQuery({
    queryKey: ['announcements'],
    queryFn: () => fetchAnnouncements(),
  })

  if (isLoading) return <Skeleton className="h-32 w-full" />
  if (!data || data.announcements.length === 0) return null

  return (
    <Panel>
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="text-sm font-medium">What changed about what you own</h2>
        <p className="text-xs text-muted-foreground">Last six months</p>
      </div>

      <ul className="flex flex-col divide-y border-y">
        {data.announcements.map((a) => (
          <li
            key={`${a.symbol}-${a.published}-${a.category}`}
            className="flex flex-col gap-1 py-3"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
              <span className="font-medium">{a.company}</span>
              <span className="text-xs text-muted-foreground">
                {daysAgo(a.published)}
              </span>
            </div>
            <p className="text-sm">{shortCategory(a.category)}</p>
            {a.summary && (
              <p className="max-w-3xl text-sm text-muted-foreground">{a.summary}</p>
            )}
            {a.attachment && (
              <a
                href={a.attachment}
                target="_blank"
                rel="noreferrer noopener"
                className="w-fit text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
              >
                The filing itself
              </a>
            )}
          </li>
        ))}
      </ul>

      <p className="max-w-3xl text-sm text-muted-foreground">
        {/* Counted, not hidden. A screen showing four of a hundred should say
            what happened to the other ninety-six. */}
        {data.filtered_out > 0 && (
          <>
            <span className="tnum">{data.filtered_out}</span> routine filings over
            the same period are not shown — conference-call notices, investor
            presentations, newspaper copies of announcements already here.{' '}
          </>
        )}
        {data.withheld > 0 && (
          <>
            <span className="tnum">{data.withheld}</span> more material filings
            are older, or are further notices from a company already listed
            above.{' '}
          </>
        )}
        None of this is a reason to trade. It is a reason to re-read something you
        already own.
      </p>

      {Object.keys(data.not_covered).length > 0 && (
        <p className="max-w-3xl text-sm text-muted-foreground">
          Not checked:{' '}
          {Object.entries(data.not_covered)
            .map(([name, reason]) => `${name} — ${reason}`)
            .join('; ')}
          .
        </p>
      )}
    </Panel>
  )
}
