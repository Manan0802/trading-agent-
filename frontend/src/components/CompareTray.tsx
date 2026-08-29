/**
 * Two or three funds side by side, on the axes that decide between them.
 *
 * A ranked list answers "which is best" and buries "how do these two differ".
 * That second question is the one somebody actually has when they are down to a
 * shortlist, and today the only way to answer it is to open two tabs and look
 * back and forth.
 *
 * **Capped at four.** Not a rendering limit — a comparison of eight funds is a
 * table, and a table is the thing they were already looking at. Four fits on a
 * phone without scrolling sideways, which is where the decision usually happens.
 *
 * **Rows are ordered by what the evidence supports.** Cost first, because it is
 * the one signal this app has measured. Past return is present and LAST, and
 * carries the reason it is not first — putting it at the top would undo §1.1
 * with layout.
 */
import { Link } from 'react-router-dom'
import type { ScreenedFund } from '@/lib/screener-api'
import { Button } from '@/components/ui/button'

export const COMPARE_LIMIT = 4

type Row = {
  label: string
  note?: string
  value: (f: ScreenedFund) => string
  lowerIsBetter?: boolean
  raw: (f: ScreenedFund) => number | null
}

const NA = 'n/a'

/** Never "0" for a figure we do not have. §14. */
function pct(v: number | null, digits = 1): string {
  return v === null || v === undefined ? NA : `${v.toFixed(digits)}%`
}

export const COMPARE_ROWS: Row[] = [
  {
    label: 'Category rank',
    note: 'against its own peers, not the whole universe',
    value: (f) =>
      f.category_rank && f.peer_size ? `${f.category_rank} of ${f.peer_size}` : NA,
    raw: (f) => (f.category_rank ? f.category_rank : null),
    lowerIsBetter: true,
  },
  {
    label: 'Risk score',
    value: (f) => (f.risk_score === null ? NA : f.risk_score.toFixed(0)),
    raw: (f) => f.risk_score,
    lowerIsBetter: true,
  },
  {
    label: 'Worst fall',
    note: 'the deepest it has been below its own peak',
    value: (f) => pct(f.max_drawdown),
    raw: (f) => f.max_drawdown,
  },
  {
    label: 'History',
    note: 'a short record is not a good one or a bad one — it is a short one',
    value: (f) => (f.history_years === null ? NA : `${f.history_years.toFixed(1)} yr`),
    raw: (f) => f.history_years,
  },
  {
    label: 'Past 3 years',
    note: 'last, on purpose: ranking funds by past return put the worse quartile on top',
    value: (f) => pct(f.returns_3y),
    raw: (f) => f.returns_3y,
  },
]

export function CompareTray({
  funds,
  onRemove,
  onClear,
}: {
  funds: ScreenedFund[]
  onRemove: (schemeCode: string) => void
  onClear: () => void
}) {
  if (funds.length === 0) return null

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 backdrop-blur">
      <div className="mx-auto max-w-[100rem] px-4 py-3 sm:px-6">
        <div className="mb-2 flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            Comparing {funds.length} of {COMPARE_LIMIT}
          </p>
          <Button variant="ghost" size="sm" onClick={onClear}>
            Clear
          </Button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-sm">
            <thead>
              <tr>
                <th className="w-40 pb-2 text-left text-xs font-normal text-muted-foreground">
                  &nbsp;
                </th>
                {funds.map((f) => (
                  <th key={f.scheme_code} className="pb-2 text-left align-top">
                    <Link
                      to={`/screener/fund/${f.scheme_code}`}
                      className="line-clamp-2 text-xs font-medium underline-offset-2 hover:underline"
                    >
                      {f.name}
                    </Link>
                    <button
                      type="button"
                      onClick={() => onRemove(f.scheme_code)}
                      className="mt-0.5 text-[10px] text-muted-foreground hover:text-foreground"
                      aria-label={`Remove ${f.name} from the comparison`}
                    >
                      remove
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COMPARE_ROWS.map((row) => {
                const values = funds.map(row.raw)
                const known = values.filter((v): v is number => v !== null)
                // Only mark a best when there is something to compare it
                // against. One known value among four blanks is not a winner.
                const best =
                  known.length >= 2
                    ? row.lowerIsBetter
                      ? Math.min(...known)
                      : Math.max(...known)
                    : null
                return (
                  <tr key={row.label} className="border-t">
                    <th className="py-1.5 pr-3 text-left align-top text-xs font-normal text-muted-foreground">
                      {row.label}
                      {row.note && (
                        <span className="block text-[10px] leading-tight opacity-80">
                          {row.note}
                        </span>
                      )}
                    </th>
                    {funds.map((f, i) => (
                      <td
                        key={f.scheme_code}
                        className={`num py-1.5 pr-3 align-top ${
                          best !== null && values[i] === best ? 'font-semibold' : ''
                        }`}
                      >
                        {row.value(f)}
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
