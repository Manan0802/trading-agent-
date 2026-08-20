import { Fragment, useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Metric, MetricRow } from '@/components/ui/metric'
import { Notice } from '@/components/ui/notice'
import { Panel } from '@/components/ui/panel'
import { Plain } from '@/components/ui/plain'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  NO_VALUE,
  categoryGroup,
  formatPercent,
  formatRatio,
  gainClass,
  plainProse,
} from '@/lib/format'
import {
  fetchAllFunds,
  fetchScreenerCategories,
  fetchTopFunds,
  type ScreenedFund,
  type ScreenerCoverage,
  type ScreenerFilters,
} from '@/lib/screener-api'
import { cn } from '@/lib/utils'

/**
 * fund_score, peer_median and the two signals all arrive between 0 and 1. This
 * is the only place in the app that multiplies one by a hundred, so there is
 * exactly one thing to correct if the API ever changes its mind.
 */
function score100(value: number | null): string {
  if (value === null || value === undefined) return NO_VALUE
  return (value * 100).toFixed(0)
}

function count(value: number | null): string {
  if (value === null || value === undefined) return NO_VALUE
  return value.toLocaleString('en-IN')
}

/** "a, b and c", because a list rendered with commas alone reads as a fragment. */
function joinWords(items: string[]): string {
  if (items.length <= 1) return items[0] ?? ''
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}

// Nulls sink in BOTH directions, so this cannot fold into the sign flip.
function cmp(a: number | null, b: number | null, dir: 1 | -1) {
  if (a === null && b === null) return 0
  if (a === null) return 1
  if (b === null) return -1
  return (a - b) * dir
}

/**
 * Every column a person can order the table by. Typed off the row rather than
 * as strings so `tsc -b` refuses a key that does not exist — the only automated
 * check the frontend has against a renamed field.
 */
type SortKey = keyof Pick<
  ScreenedFund,
  | 'fund_score'
  | 'returns_1m'
  | 'returns_3m'
  | 'returns_6m'
  | 'returns_1y'
  | 'returns_3y'
  | 'rolling_1m'
  | 'rolling_3m'
  | 'rolling_6m'
  | 'rolling_1y'
  | 'rolling_3y'
  | 'sortino'
  | 'volatility'
  | 'max_drawdown'
  | 'worst_30d'
  | 'momentum_signal'
  | 'drawdown_signal'
  | 'peer_median'
>

type GroupKey = 'returns' | 'rolling' | 'risk' | 'signals' | 'all'

type Column = {
  id: string
  /** What the header says. Twenty-one of these share one row. */
  label: string
  /** What the sort button says out loud. "3M" is not a sentence. */
  longLabel: string
  sortKey: SortKey | null
  group: Exclude<GroupKey, 'all'> | 'always'
  className?: string
  /** Sign colouring, decided per row. */
  tone?: (f: ScreenedFund) => string
  cell: (f: ScreenedFund) => ReactNode
}

function pctColumn(
  key: SortKey,
  label: string,
  longLabel: string,
  group: Column['group'],
): Column {
  return {
    id: key,
    label,
    longLabel,
    sortKey: key,
    group,
    className: 'num text-right',
    tone: (f) => gainClass(f[key]),
    cell: (f) => formatPercent(f[key]),
  }
}

const COLUMNS: Column[] = [
  {
    id: 'fund_score',
    label: 'Score',
    longLabel: 'fund score',
    sortKey: 'fund_score',
    group: 'always',
    className: 'num text-right font-medium',
    cell: (f) => score100(f.fund_score),
  },
  {
    id: 'grade',
    label: 'Grade',
    longLabel: 'grade',
    sortKey: null,
    group: 'always',
    className: 'text-right',
    cell: (f) =>
      f.grade ? (
        <Badge
          variant={
            f.grade === 'Very Good' ? 'default' : f.grade === 'Good' ? 'secondary' : 'outline'
          }
        >
          {f.grade}
        </Badge>
      ) : (
        NO_VALUE
      ),
  },

  pctColumn('returns_1m', '1M', 'the last month', 'returns'),
  pctColumn('returns_3m', '3M', 'the last three months', 'returns'),
  pctColumn('returns_6m', '6M', 'the last six months', 'returns'),
  pctColumn('returns_1y', '1Y', 'the last year', 'returns'),
  pctColumn('returns_3y', '3Y', 'the last three years', 'returns'),

  pctColumn('rolling_1m', 'Roll 1M', 'the average month', 'rolling'),
  pctColumn('rolling_3m', 'Roll 3M', 'the average three months', 'rolling'),
  pctColumn('rolling_6m', 'Roll 6M', 'the average six months', 'rolling'),
  pctColumn('rolling_1y', 'Roll 1Y', 'the average year', 'rolling'),
  pctColumn('rolling_3y', 'Roll 3Y', 'the average three years', 'rolling'),

  {
    id: 'sortino',
    label: 'Sortino',
    longLabel: 'return per unit of downside',
    sortKey: 'sortino',
    group: 'risk',
    className: 'num text-right',
    cell: (f) => formatRatio(f.sortino),
  },
  {
    id: 'volatility',
    label: 'Volatility',
    longLabel: 'how much the price moves about',
    sortKey: 'volatility',
    group: 'risk',
    className: 'num text-right text-muted-foreground',
    cell: (f) => formatPercent(f.volatility, { signed: false }),
  },
  pctColumn('max_drawdown', 'Worst fall', 'the worst fall from a peak', 'risk'),
  pctColumn('worst_30d', 'Worst month', 'the worst thirty days', 'risk'),
  {
    id: 'risk_tier',
    label: 'Risk',
    longLabel: 'risk tier',
    sortKey: null,
    group: 'risk',
    className: 'text-right text-muted-foreground',
    cell: (f) => f.risk_tier ?? NO_VALUE,
  },

  {
    id: 'momentum_signal',
    label: 'Momentum',
    longLabel: 'the momentum signal',
    sortKey: 'momentum_signal',
    group: 'signals',
    className: 'num text-right',
    cell: (f) => score100(f.momentum_signal),
  },
  {
    id: 'drawdown_signal',
    label: 'Fall pressure',
    longLabel: 'drawdown pressure',
    sortKey: 'drawdown_signal',
    group: 'signals',
    className: 'num text-right',
    cell: (f) => score100(f.drawdown_signal),
  },
  {
    id: 'peer_median',
    label: 'Peer median',
    longLabel: 'the middle score of its peer group',
    sortKey: 'peer_median',
    group: 'signals',
    className: 'num text-right text-muted-foreground',
    cell: (f) => score100(f.peer_median),
  },
  {
    id: 'peer_size',
    label: 'Peers',
    // Not sortable: this is a property of the category, not a measurement of
    // the fund, so ordering the whole universe by it says nothing.
    longLabel: 'how many funds it is ranked against',
    sortKey: null,
    group: 'signals',
    className: 'num text-right text-muted-foreground',
    cell: (f) => count(f.peer_size),
  },
]

const GROUP_LABELS: { value: GroupKey; label: string }[] = [
  { value: 'returns', label: 'Returns' },
  { value: 'rolling', label: 'Rolling returns' },
  { value: 'risk', label: 'Risk' },
  { value: 'signals', label: 'Signals' },
  { value: 'all', label: 'Everything' },
]

function visibleColumns(group: GroupKey): Column[] {
  if (group === 'all') return COLUMNS
  return COLUMNS.filter((c) => c.group === 'always' || c.group === group)
}

/** Every field on a row except the pre-written sentences, which do not fit a cell. */
const CSV_FIELDS: (keyof Omit<ScreenedFund, 'reasons'>)[] = [
  'rank',
  'category_rank',
  'scheme_code',
  'name',
  'fund_house',
  'category',
  'sub_category',
  'asset_class',
  'fund_score',
  'grade',
  'peer_median',
  'peer_size',
  'returns_1m',
  'returns_3m',
  'returns_6m',
  'returns_1y',
  'returns_3y',
  'rolling_1m',
  'rolling_3m',
  'rolling_6m',
  'rolling_1y',
  'rolling_3y',
  'sortino',
  'volatility',
  'max_drawdown',
  'worst_30d',
  'momentum_signal',
  'drawdown_signal',
  'risk_score',
  'risk_tier',
  'history_years',
  'nav_rows',
  'is_new',
]

/**
 * Built and thrown away inside the click. An `<a download>` sitting in the
 * markup would be one more `a[href]` the phone harness measures, and it would
 * have to be 32px square to earn its place on the page.
 */
function downloadCsv(rows: ScreenedFund[], asOf: string) {
  const escape = (value: unknown) => {
    const s = value === null || value === undefined ? '' : String(value)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const csv = [
    CSV_FIELDS.join(','),
    ...rows.map((r) => CSV_FIELDS.map((f) => escape(r[f])).join(',')),
  ].join('\n')

  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `nextrade-screener-${asOf}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

/** One labelled native select. Native because it is the only picker a thumb never misses. */
function Field({
  id,
  label,
  value,
  onChange,
  children,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  children: ReactNode
}) {
  return (
    <div className="flex w-full min-w-0 max-w-full flex-col gap-1.5 sm:w-auto">
      <Label htmlFor={id}>{label}</Label>
      <select
        id={id}
        // h-9, never h-8: h-8 is exactly the 32px tap-target floor, and a
        // control that passes with zero margin fails on a font-metrics change.
        className="h-9 w-full max-w-full rounded-md border bg-transparent px-2 text-sm sm:w-auto sm:min-w-40"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {children}
      </select>
    </div>
  )
}

/**
 * The scheme name, its position and its house, in the one column that stays
 * put while the other twenty-one scroll past it.
 *
 * `bg-card` sits on the row and `bg-inherit` on this cell: `bg-card` here would
 * kill the hover tint and leave a seam, and `bg-inherit` on a transparent row
 * lets the scrolling columns show through. The row's hover is forced to opaque
 * `bg-muted` for the same reason — the stock `bg-muted/50` is translucent.
 */
function NameCell({
  fund,
  position,
  isOpen,
  onToggle,
}: {
  fund: ScreenedFund
  position: number
  isOpen: boolean
  onToggle: () => void
}) {
  return (
    <TableCell className="sticky left-0 z-10 bg-inherit align-top whitespace-normal shadow-[inset_-1px_0_0_0_var(--border)]">
      {/* A fixed inner width, because max-width does not apply to a table cell
          in an auto-layout table and the name would otherwise take the row. */}
      <div className="flex w-40 items-start gap-2.5 sm:w-72">
        <span className="num w-6 shrink-0 pt-1.5 text-right text-xs text-muted-foreground">
          {position > 0 ? position : NO_VALUE}
        </span>
        <span className="min-w-0">
          <button
            type="button"
            aria-expanded={isOpen}
            onClick={onToggle}
            // A one-line 14px name is an 18px-tall target. min-h-9 gives it the
            // full 36px and the negative margin hands the extra back to the row.
            className="-my-2 flex min-h-9 w-fit items-center text-left text-sm font-medium leading-tight underline-offset-4 hover:underline"
          >
            {fund.name}
          </button>
          <span className="mt-1 block text-xs text-muted-foreground">
            {fund.fund_house}
            {fund.is_new ? ' · too new to rank' : ''}
          </span>
        </span>
      </div>
    </TableCell>
  )
}

/** Why this fund is where it is, and every figure behind it. */
function DetailRow({ fund, span }: { fund: ScreenedFund; span: number }) {
  return (
    <TableRow className="bg-card hover:bg-card">
      <TableCell colSpan={span} className="p-0 whitespace-normal">
        {/* Sticks to the left edge of the scroller so the reasoning stays
            readable however far right the table has been dragged. */}
        <div className="sticky left-0 flex w-[19rem] flex-col gap-5 p-2 pb-6 sm:w-[46rem] lg:w-[64rem]">
          {fund.reasons.length > 0 ? (
            <ul className="grid gap-x-10 gap-y-2 xl:grid-cols-2">
              {fund.reasons.map((reason) => (
                <li key={reason.kind} className="flex gap-2 text-sm">
                  <span aria-hidden className="text-muted-foreground">
                    &middot;
                  </span>
                  <span>{reason.text}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              Nothing here stands out against its peers, which is the honest answer for
              most funds. A bullet only appears when a fund is genuinely near the top of
              its own group.
            </p>
          )}

          <MetricRow>
            <Metric label="Score" value={score100(fund.fund_score)} size="sm" hint="Out of 100" />
            <Metric label="Grade" value={fund.grade ?? NO_VALUE} size="sm" />
            <Metric
              label="In its category"
              value={fund.category_rank > 0 ? `#${fund.category_rank}` : NO_VALUE}
              size="sm"
              hint={`${fund.sub_category}, ${count(fund.peer_size)} funds`}
            />
            <Metric
              label="Peer median"
              value={score100(fund.peer_median)}
              size="sm"
              hint="The middle score of that group"
            />

            <Metric label="1 month" value={formatPercent(fund.returns_1m)} size="sm" />
            <Metric label="3 months" value={formatPercent(fund.returns_3m)} size="sm" />
            <Metric label="6 months" value={formatPercent(fund.returns_6m)} size="sm" />
            <Metric label="1 year" value={formatPercent(fund.returns_1y)} size="sm" />
            <Metric label="3 years" value={formatPercent(fund.returns_3y)} size="sm" />

            <Metric label="Rolling 1 month" value={formatPercent(fund.rolling_1m)} size="sm" />
            <Metric label="Rolling 3 months" value={formatPercent(fund.rolling_3m)} size="sm" />
            <Metric label="Rolling 6 months" value={formatPercent(fund.rolling_6m)} size="sm" />
            <Metric label="Rolling 1 year" value={formatPercent(fund.rolling_1y)} size="sm" />
            <Metric label="Rolling 3 years" value={formatPercent(fund.rolling_3y)} size="sm" />

            <Metric label="Sortino" value={formatRatio(fund.sortino)} size="sm" />
            <Metric
              label="Volatility"
              value={formatPercent(fund.volatility, { signed: false })}
              size="sm"
            />
            <Metric label="Worst fall" value={formatPercent(fund.max_drawdown)} size="sm" />
            <Metric label="Worst 30 days" value={formatPercent(fund.worst_30d)} size="sm" />

            <Metric label="Momentum" value={score100(fund.momentum_signal)} size="sm" />
            <Metric label="Fall pressure" value={score100(fund.drawdown_signal)} size="sm" />
            <Metric
              label="Risk"
              value={score100(fund.risk_score)}
              size="sm"
              hint={fund.risk_tier ?? undefined}
            />
            <Metric
              label="Record"
              value={fund.history_years === null ? NO_VALUE : `${fund.history_years.toFixed(1)}y`}
              size="sm"
              hint={`${count(fund.nav_rows)} published NAVs`}
            />
          </MetricRow>
        </div>
      </TableCell>
    </TableRow>
  )
}

function HeadRow({
  columns,
  sort,
  onSort,
}: {
  columns: Column[]
  sort: { key: SortKey; dir: 1 | -1 } | null
  /** Omitted on the grouped view, where the order is stated and nothing to sort. */
  onSort?: (key: SortKey) => void
}) {
  return (
    <TableRow className="bg-card hover:bg-card">
      <TableHead className="sticky left-0 z-10 bg-inherit shadow-[inset_-1px_0_0_0_var(--border)]">
        <span className="block w-40 sm:w-72">Rank and scheme</span>
      </TableHead>
      {columns.map((column) => {
        const key = column.sortKey
        const dir = key !== null && sort !== null && sort.key === key ? sort.dir : null
        return (
          <TableHead
            key={column.id}
            className="text-right"
            aria-sort={dir === null ? 'none' : dir === 1 ? 'ascending' : 'descending'}
          >
            {onSort && key ? (
              <button
                type="button"
                onClick={() => onSort(key)}
                // A <th> reading "1M" is 22px of text, which fails the phone
                // harness on WIDTH long before it fails on height.
                className="inline-flex min-h-9 min-w-9 items-center justify-end gap-1 px-1 hover:underline"
                aria-label={`Sort by ${column.longLabel}, ${
                  dir === -1 ? 'ascending' : 'descending'
                }`}
              >
                <span>{column.label}</span>
                <ChevronDown
                  aria-hidden
                  className={cn(
                    'size-3 shrink-0 transition-transform',
                    dir === null ? 'opacity-0' : dir === 1 ? 'rotate-180' : '',
                  )}
                />
              </button>
            ) : (
              column.label
            )}
          </TableHead>
        )
      })}
    </TableRow>
  )
}

/** The shared scroller. Exactly -mx-4, so it cancels the Panel's p-4 and no more. */
function TableScroller({ children }: { children: ReactNode }) {
  return <div className="-mx-4 overflow-x-auto sm:mx-0">{children}</div>
}

function ScreenerLoading() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-[32rem] w-full" />
    </div>
  )
}

function errorSentence(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return plainProse(
    detail ??
      'The fund screener is not answering right now. Refresh the page, and if it keeps failing the NAV feed is down rather than your connection.',
  )
}

/** Everything the run itself admits to. Always rendered, never behind a tab. */
function CoveragePanel({ coverage, shown }: { coverage: ScreenerCoverage; shown: number }) {
  const grouped = new Map<string, number>()
  for (const item of coverage.unscorable) {
    // The dates and category names differ per fund; the four underlying
    // reasons do not, and four lines are readable where two hundred are not.
    const reason = item.reason
      .replace(/'[^']*'/, 'from before 2018')
      .replace(/\d{4}-\d{2}-\d{2}/, 'a long time ago')
    grouped.set(reason, (grouped.get(reason) ?? 0) + 1)
  }
  const unscored = coverage.universe - coverage.scored

  return (
    <Panel title="What this covers">
      <p className="max-w-3xl text-sm">
        Showing <span className="tnum">{count(shown)}</span> of{' '}
        <span className="tnum">{count(coverage.scored)}</span> scored funds, drawn from{' '}
        <span className="tnum">{count(coverage.universe)}</span> in the AMFI list.{' '}
        <span className="tnum">{coverage.categories_ranked}</span> of{' '}
        <span className="tnum">{coverage.categories_total}</span> categories are ranked. Figures as
        of <span className="tnum">{coverage.as_of}</span>.
      </p>

      {coverage.stale_days > 3 && (
        <Notice>
          These figures are {coverage.stale_days} days old. NAVs are published every business day,
          so something upstream has stopped updating and this is not today&rsquo;s ranking.
        </Notice>
      )}

      {coverage.missing_columns.length > 0 && (
        <p className="max-w-3xl text-sm text-muted-foreground">
          {joinWords(coverage.missing_columns)}{' '}
          {coverage.missing_columns.length === 1 ? 'is' : 'are'} not shown, we have no reliable
          source for {coverage.missing_columns.length === 1 ? 'it' : 'them'}.
        </p>
      )}

      {coverage.thin_categories.length > 0 && (
        <p className="max-w-3xl text-sm text-muted-foreground">
          {coverage.thin_categories.length} categories are too small to rank anybody in:{' '}
          {joinWords(
            coverage.thin_categories.map((c) => `${c.sub_category} (${c.peer_size} funds)`),
          )}
          .
        </p>
      )}

      {coverage.unscorable.length > 0 && (
        <Plain
          label="why they were left out"
          detail={
            <ul className="flex flex-col gap-1">
              {[...grouped.entries()].map(([reason, n]) => (
                <li key={reason}>
                  <span className="tnum">{n}</span> {reason}
                </li>
              ))}
            </ul>
          }
        >
          <span className="tnum">{count(unscored)}</span> funds in the list could not be scored at
          all. Most are dead schemes or pre-2018 category labels; a sample of{' '}
          <span className="tnum">{coverage.unscorable.length}</span> is broken down below.
        </Plain>
      )}
    </Panel>
  )
}

function MethodPanel() {
  return (
    <Panel title="How this is worked out">
      <Plain
        label="what the score is made of"
        detail={
          <div className="flex flex-col gap-2">
            <p>
              The score arrives from the API between 0 and 1 and is shown here out of 100. It is
              built from the columns on this page: trailing returns over 1M, 3M, 6M, 1Y and 3Y, the
              same five windows averaged over every possible start date, a momentum signal and a
              drawdown signal. Each is ranked inside the fund&rsquo;s own SEBI sub-category, never
              across the whole market.
            </p>
            <p>
              Peer median is the middle score of that same group, so a fund above it beat half its
              peers. Grade is a band of the score: Very Good, Good, Avg, Bad. Volatility, worst fall
              and worst 30 days are fractions of NAV. Sortino is a bare ratio, return per unit of
              downside.
            </p>
          </div>
        }
      >
        Every fund is judged on its own record, how consistently it has done well, how much it
        returned and how rough the ride was. The score is a position inside its peer group rather
        than an absolute mark, so a Very Good liquid fund and a Very Good small cap fund are good at
        completely different things. A fund only earns a bullet point when it is genuinely near the
        top of its group, and most funds get none.
      </Plain>
      <p className="max-w-3xl text-sm text-muted-foreground">
        Research ranks funds by cost, which is the thing we measured that predicts returns; this
        screener ranks them by track record, which is the industry-standard method. The same fund
        can be first on one and twenty-second on the other, and that disagreement is the point.
      </p>
    </Panel>
  )
}

/* ------------------------------------------------------------------ mode A */

function TopFundsView({
  filters,
  perCategory,
  group,
  openCode,
  onToggle,
  onShowAll,
}: {
  filters: ScreenerFilters
  perCategory: number
  group: GroupKey
  openCode: string | null
  onToggle: (code: string) => void
  onShowAll: () => void
}) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['screener-top', filters, perCategory],
    queryFn: () => fetchTopFunds({ ...filters, per_category: perCategory }),
    retry: false,
  })

  const columns = visibleColumns(group)
  const span = columns.length + 1

  if (isLoading) return <ScreenerLoading />
  if (isError || !data) return <Notice>{errorSentence(error)}</Notice>
  if (data.groups.length === 0) {
    return <Notice>Nothing matches those filters. Widen one of them and try again.</Notice>
  }

  const shown = data.groups.reduce((n, g) => n + g.funds.length, 0)
  const filtered = Object.values(filters).some(Boolean)

  return (
    <>
      {data.dominance.length > 0 && (
        <Panel title="What is crowding the top">
          <ul className="flex flex-col gap-2">
            {data.dominance.map((d) => (
              <li key={`${d.asset_class}-${d.sub_category}`} className="max-w-3xl text-sm">
                <span className="tnum font-medium">
                  {d.count} of the top {d.of}
                </span>{' '}
                {d.asset_class} funds are {d.sub_category} funds, about{' '}
                <span className="tnum">{d.lift.toFixed(1)}</span> times their share of the{' '}
                {d.asset_class} universe.
              </li>
            ))}
          </ul>
          <p className="max-w-3xl text-sm text-muted-foreground">
            A category running hot is a fact about the last year, not about how those funds are run.
          </p>
        </Panel>
      )}

      <Panel
        title="Top funds in each category"
        aside={`Best ${perCategory} by score in each of ${data.groups.length} categories`}
      >
        <TableScroller>
          <Table>
            <TableHeader>
              <HeadRow columns={columns} sort={null} />
            </TableHeader>
            <TableBody>
              {data.groups.map((g) => (
                <Fragment key={`${g.category}-${g.sub_category}`}>
                  <TableRow className="bg-card hover:bg-card">
                    {/* A heading element here would give h1 -> h3 inside a
                        Panel that already owns the h2. A colgroup header is
                        what a screen reader wants from a table anyway. */}
                    <th
                      scope="colgroup"
                      colSpan={span}
                      className="px-2 pt-7 pb-2 text-left align-bottom font-medium"
                    >
                      {/* Sticks to the left edge of the scroller: without it
                          you drag right past Sortino and no longer know which
                          category the five rows under you belong to. */}
                      <span className="sticky left-0 block w-[19rem] sm:w-[46rem] lg:w-[64rem]">
                        <span className="text-sm">
                          {categoryGroup(g.category)} &middot; {g.sub_category}
                        </span>
                        <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                          <span className="tnum">{g.peer_size}</span> funds ranked against each
                          other
                          {g.caveat ? `. ${g.caveat}` : ''}
                        </span>
                      </span>
                    </th>
                  </TableRow>
                  {g.funds.map((f) => (
                    <FundRows
                      key={f.scheme_code}
                      fund={f}
                      position={f.category_rank}
                      columns={columns}
                      span={span}
                      isOpen={openCode === f.scheme_code}
                      onToggle={() => onToggle(f.scheme_code)}
                    />
                  ))}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </TableScroller>
        <div>
          <Button variant="outline" size="lg" onClick={onShowAll}>
            {filtered
              ? 'Show every fund that matches'
              : `Show all ${count(data.coverage.scored)} funds`}
          </Button>
        </div>
      </Panel>

      <CoveragePanel coverage={data.coverage} shown={shown} />
    </>
  )
}

/* ------------------------------------------------------------------ mode B */

const PAGE_SIZE = 100

function AllFundsView({
  filters,
  group,
  openCode,
  onToggle,
  onBack,
}: {
  filters: ScreenerFilters
  group: GroupKey
  openCode: string | null
  onToggle: (code: string) => void
  onBack: () => void
}) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 } | null>(null)
  const [page, setPage] = useState(0)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['screener-all', filters],
    queryFn: () => fetchAllFunds({ ...filters, include_new: true }),
    retry: false,
  })

  const rows = useMemo(
    () => (data ? [...data.funds, ...data.new_funds] : []),
    [data],
  )

  const sorted = useMemo(() => {
    if (!sort) return rows
    // Never in place: React Query hands back the cached array, and mutating it
    // makes the # column drift on an unrelated refetch.
    return [...rows].sort((a, b) => cmp(a[sort.key], b[sort.key], sort.dir))
  }, [rows, sort])

  const columns = visibleColumns(group)
  const span = columns.length + 1

  if (isLoading) return <ScreenerLoading />
  if (isError || !data) return <Notice>{errorSentence(error)}</Notice>

  // 1,689 rows across 21 columns is forty thousand nodes; the page stops
  // responding and the accessibility walk times out. A hundred at a time is
  // the whole reason this view is usable.
  const lastPage = Math.max(0, Math.ceil(sorted.length / PAGE_SIZE) - 1)
  const safePage = Math.min(page, lastPage)
  const from = safePage * PAGE_SIZE
  const visible = sorted.slice(from, from + PAGE_SIZE)

  function onSort(key: SortKey) {
    setPage(0)
    setSort((s) => (s?.key === key ? { key, dir: s.dir === -1 ? 1 : -1 } : { key, dir: -1 }))
  }

  return (
    <>
      <Panel
        title="Every scored fund"
        aside={
          sort
            ? 'Sorted by the column you chose; the number stays the universe rank'
            : 'In universe rank order'
        }
      >
        {sorted.length === 0 ? (
          <Notice>Nothing matches those filters. Widen one of them and try again.</Notice>
        ) : (
          <>
            <TableScroller>
              <Table>
                <TableHeader>
                  <HeadRow columns={columns} sort={sort} onSort={onSort} />
                </TableHeader>
                <TableBody>
                  {visible.map((f) => (
                    <FundRows
                      key={f.scheme_code}
                      fund={f}
                      position={f.rank}
                      columns={columns}
                      span={span}
                      isOpen={openCode === f.scheme_code}
                      onToggle={() => onToggle(f.scheme_code)}
                    />
                  ))}
                </TableBody>
              </Table>
            </TableScroller>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">
                Rows <span className="tnum">{count(from + 1)}</span> to{' '}
                <span className="tnum">{count(from + visible.length)}</span> of{' '}
                <span className="tnum">{count(sorted.length)}</span>
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  size="lg"
                  disabled={safePage === 0}
                  onClick={() => setPage(safePage - 1)}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="lg"
                  disabled={safePage >= lastPage}
                  onClick={() => setPage(safePage + 1)}
                >
                  Next
                </Button>
                <Button
                  variant="outline"
                  size="lg"
                  onClick={() => downloadCsv(sorted, data.coverage.as_of)}
                >
                  Download CSV
                </Button>
                <Button variant="ghost" size="lg" onClick={onBack}>
                  Back to the leaders
                </Button>
              </div>
            </div>
          </>
        )}
      </Panel>

      <CoveragePanel coverage={data.coverage} shown={sorted.length} />
    </>
  )
}

/** A fund's row, plus its reasoning underneath when it is the open one. */
function FundRows({
  fund,
  position,
  columns,
  span,
  isOpen,
  onToggle,
}: {
  fund: ScreenedFund
  position: number
  columns: Column[]
  span: number
  isOpen: boolean
  onToggle: () => void
}) {
  return (
    <>
      <TableRow className="bg-card hover:bg-muted has-aria-expanded:bg-muted">
        <NameCell fund={fund} position={position} isOpen={isOpen} onToggle={onToggle} />
        {columns.map((column) => (
          <TableCell
            key={column.id}
            className={cn('align-top', column.className, column.tone?.(fund))}
          >
            {column.cell(fund)}
          </TableCell>
        ))}
      </TableRow>
      {isOpen && <DetailRow fund={fund} span={span} />}
    </>
  )
}

/* -------------------------------------------------------------------- page */

export function Screener() {
  const [params, setParams] = useSearchParams()
  // The sub-view lives in the URL rather than in state: every harness on this
  // project addresses a page by its path, so a view only reachable by clicking
  // a tab is untested by construction. Phases 5 and 6 add ?tab=, which is why
  // the existing params are carried through rather than replaced.
  const view = params.get('view') === 'all' ? 'all' : 'top'

  const [filters, setFilters] = useState<ScreenerFilters>({})
  const [perCategory, setPerCategory] = useState(5)
  const [openCode, setOpenCode] = useState<string | null>(null)
  const [group, setGroup] = useState<GroupKey>(() =>
    // Read once, at mount. matchMedia in an initialiser does NOT react to a
    // resize — this is a starting point chosen from the screen you arrived on,
    // not a responsive binding. There is no SSR here, so window always exists.
    window.matchMedia('(min-width: 1280px)').matches ? 'all' : 'returns',
  )

  const { data: meta } = useQuery({
    queryKey: ['screener-categories'],
    queryFn: fetchScreenerCategories,
    retry: false,
  })

  function setView(next: 'top' | 'all') {
    const nextParams = new URLSearchParams(params)
    if (next === 'all') nextParams.set('view', 'all')
    else nextParams.delete('view')
    setParams(nextParams)
    setOpenCode(null)
  }

  function setFilter(key: keyof ScreenerFilters, value: string) {
    setFilters((f) => ({ ...f, [key]: value }))
    setOpenCode(null)
  }

  const byGroup = new Map<string, string[]>()
  for (const c of meta?.categories ?? []) {
    const key = categoryGroup(c.category)
    byGroup.set(key, [...(byGroup.get(key) ?? []), c.sub_category])
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Outside every loading branch on purpose. Panel emits an h2, so a page
          whose h1 only appears once the data lands starts at h2 while it is
          fetching, and the heading order check fails on the loading state. */}
      <header className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Top funds</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Every Indian mutual fund with enough NAV history to judge, scored on its record and ranked
          inside its own category. Worked out by NexTrade from public data, not a licensed rating,
          and not a recommendation to buy.
        </p>
      </header>

      <Panel className="flex-row flex-wrap items-end gap-x-6 gap-y-3">
        <Field
          id="screener-category"
          label="Category"
          value={filters.category ?? ''}
          onChange={(v) => setFilter('category', v)}
        >
          <option value="">Every category</option>
          {[...byGroup.entries()].map(([name, subs]) => (
            <optgroup key={name} label={name}>
              {subs.map((sub) => (
                <option key={sub} value={sub}>
                  {sub}
                </option>
              ))}
            </optgroup>
          ))}
        </Field>

        <Field
          id="screener-asset-class"
          label="Asset class"
          value={filters.asset_class ?? ''}
          onChange={(v) => setFilter('asset_class', v)}
        >
          <option value="">Every asset class</option>
          {(meta?.asset_classes ?? []).map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </Field>

        <Field
          id="screener-grade"
          label="Grade"
          value={filters.grade ?? ''}
          onChange={(v) => setFilter('grade', v)}
        >
          <option value="">Every grade</option>
          {(meta?.grades ?? []).map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </Field>

        <Field
          id="screener-risk-tier"
          label="Risk"
          value={filters.risk_tier ?? ''}
          onChange={(v) => setFilter('risk_tier', v)}
        >
          <option value="">Every risk tier</option>
          {(meta?.risk_tiers ?? []).map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </Field>

        {view === 'top' && (
          <Field
            id="screener-per-category"
            label="Leaders per category"
            value={String(perCategory)}
            onChange={(v) => {
              setPerCategory(Number(v))
              setOpenCode(null)
            }}
          >
            {/* The API allows 25. Thirty-six categories at 25 is nine hundred
                rows across twenty-one columns, which is a page that stops
                scrolling smoothly, so this stops at ten. */}
            {[1, 3, 5, 10].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </Field>
        )}

        <Field
          id="screener-columns"
          label="Columns"
          value={group}
          onChange={(v) => setGroup(v as GroupKey)}
        >
          {GROUP_LABELS.map((g) => (
            <option key={g.value} value={g.value}>
              {g.label}
            </option>
          ))}
        </Field>
      </Panel>

      {view === 'top' ? (
        <TopFundsView
          filters={filters}
          perCategory={perCategory}
          group={group}
          openCode={openCode}
          onToggle={(code) => setOpenCode(openCode === code ? null : code)}
          onShowAll={() => setView('all')}
        />
      ) : (
        <AllFundsView
          filters={filters}
          group={group}
          openCode={openCode}
          onToggle={(code) => setOpenCode(openCode === code ? null : code)}
          onBack={() => setView('top')}
        />
      )}

      <MethodPanel />
    </div>
  )
}
