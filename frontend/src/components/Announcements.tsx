import { useQuery } from '@tanstack/react-query'
import { ExternalLink, FileText } from 'lucide-react'
import { Panel } from '@/components/ui/panel'
import { Reveal } from '@/components/ui/reveal'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchAnnouncements } from '@/lib/portfolio-api'
import { cn } from '@/lib/utils'

/**
 * What changed about the companies you own — not a news feed.
 *
 * The distinction is the whole design. Retail investors who watch more, trade
 * more, and turnover and tax are two of the few things this app has measured as
 * decisive. So there is no ticker, no market commentary and no prices here:
 * every row is a filing about something already in the portfolio, and the
 * closing line says out loud that none of it is a reason to trade.
 *
 * Each filing is a card with its own summary clamped to two lines. The full
 * text is one line away and the regulation-speak — "disclosure under Regulation
 * 30 read with Regulation 51 of the Securities and Exchange Board of India
 * (Listing Obligations and Disclosure Requirements) Regulations, 2015, as
 * amended" — is the thing NSE writes, not a thing worth three lines of a
 * dashboard.
 */

/**
 * A colour per kind of filing, so a run of them can be scanned rather than
 * read. Anything unrecognised is neutral: guessing a category from a substring
 * is how a routine notice ends up looking like a merger.
 */
function toneFor(category: string): { dot: string; ink: string } {
  const c = category.toLowerCase()
  if (c.includes('acquisition') || c.includes('merger') || c.includes('amalgamat'))
    return { dot: 'bg-v-violet', ink: 'text-v-violet-ink' }
  if (c.includes('dividend') || c.includes('bonus') || c.includes('split'))
    return { dot: 'bg-v-emerald', ink: 'text-v-emerald-ink' }
  if (c.includes('litigation') || c.includes('penalt') || c.includes('default'))
    return { dot: 'bg-v-amber', ink: 'text-v-amber-ink' }
  if (c.includes('result') || c.includes('financial'))
    return { dot: 'bg-v-cyan', ink: 'text-v-cyan-ink' }
  return { dot: 'bg-muted-foreground/50', ink: 'text-muted-foreground' }
}

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

  if (isLoading) return <Skeleton className="h-32 w-full rounded-xl" />
  if (!data || data.announcements.length === 0) return null

  const hidden = data.filtered_out + data.withheld

  return (
    <Panel title="What changed about what you own" aside="Last six months">
      <ul className="grid gap-2 lg:grid-cols-2">
        {data.announcements.map((a, i) => {
          const tone = toneFor(a.category)
          return (
            <li
              // The index, because nothing in a filing is unique. Tata Steel
              // files litigation updates twice on the same day under the same
              // category, and symbol+date+category collided on exactly that --
              // React then drops one of the two, so a real filing disappears
              // and nothing says so. The list is read-only and never reorders,
              // which is the case where an index key is the correct one.
              key={`${a.symbol}-${a.published}-${a.category}-${i}`}
              className="lift flex flex-col gap-1.5 rounded-lg border bg-muted/25 p-3.5"
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="flex items-center gap-2 truncate text-sm font-medium">
                  <span className={cn('size-1.5 shrink-0 rounded-full', tone.dot)} aria-hidden />
                  {a.company}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {daysAgo(a.published)}
                </span>
              </div>
              <p className={cn('text-xs font-semibold uppercase tracking-wide', tone.ink)}>
                {shortCategory(a.category)}
              </p>
              {a.summary && (
                // Two lines. NSE writes these at legal length and the third
                // line is always the same regulation being cited again.
                <p className="line-clamp-2 text-sm leading-snug text-muted-foreground">
                  {a.summary}
                </p>
              )}
              {a.attachment && (
                <a
                  href={a.attachment}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="inline-flex w-fit items-center gap-1 text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
                >
                  <FileText className="size-3" aria-hidden />
                  The filing itself
                  <ExternalLink className="size-3" aria-hidden />
                </a>
              )}
            </li>
          )
        })}
      </ul>

      <p className="text-sm">
        None of this is a reason to trade. It is a reason to re-read something you
        already own.
      </p>

      {(hidden > 0 || Object.keys(data.not_covered).length > 0) && (
        <Reveal
          label={
            hidden > 0
              ? `${hidden} more filings, and what we could not check`
              : 'What we could not check'
          }
        >
          {/* Counted, not hidden. A screen showing four of a hundred should say
              what happened to the other ninety-six — just not before the four. */}
          {data.filtered_out > 0 && (
            <p>
              <span className="tnum">{data.filtered_out}</span> routine filings over
              the same period are not shown &mdash; conference-call notices, investor
              presentations, newspaper copies of announcements already here.
            </p>
          )}
          {data.withheld > 0 && (
            <p>
              <span className="tnum">{data.withheld}</span> more material filings are
              older, or are further notices from a company already listed above.
            </p>
          )}
          {Object.keys(data.not_covered).length > 0 && (
            <div>
              <p className="mb-1 font-medium text-foreground">Not checked</p>
              <ul className="flex flex-col gap-1">
                {Object.entries(data.not_covered).map(([name, reason]) => (
                  <li key={name}>
                    <span className="text-foreground">{name}</span> &mdash; {reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Reveal>
      )}
    </Panel>
  )
}
