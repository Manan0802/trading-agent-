import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'

/**
 * Search AMFI by name, pick the exact scheme.
 *
 * The form used to ask for a six-digit AMFI scheme code, typed from memory.
 * Nobody knows their scheme code, and every figure in this app hangs off it
 * being right: the NAV, the return, the benchmark comparison, and the whole
 * direct-versus-regular cost review, which reads plan type from the scheme
 * rather than from what the holding was called. A wrong code does not error —
 * it quietly prices a different fund.
 *
 * Picking from the source also guarantees the stored name and the stored code
 * describe the same thing, which typing two free-text fields never could.
 */

export type PickedScheme = { scheme_code: string; scheme_name: string }

function useDebounced(value: string, ms = 300) {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return settled
}

export function FundPicker({
  picked,
  onPick,
}: {
  picked: PickedScheme | null
  onPick: (scheme: PickedScheme | null) => void
}) {
  const [query, setQuery] = useState('')
  const settled = useDebounced(query)

  const { data, isFetching, isError } = useQuery<PickedScheme[]>({
    queryKey: ['fund-search', settled],
    queryFn: async () =>
      (await api.get('/api/v1/research/funds/search', { params: { q: settled } })).data,
    // Two letters match half of AMFI and tell the reader nothing.
    enabled: settled.trim().length >= 3 && !picked,
    retry: false,
  })

  if (picked) {
    return (
      <div className="flex flex-col gap-1.5">
        <Label>Fund</Label>
        <div className="flex items-start justify-between gap-3 rounded-md border px-3 py-2">
          <span className="flex items-start gap-2">
            <Check className="mt-0.5 size-4 shrink-0 text-gain" aria-hidden />
            <span className="flex flex-col">
              <span className="text-sm leading-tight">{picked.scheme_name}</span>
              <span className="num text-xs text-muted-foreground">
                AMFI {picked.scheme_code}
              </span>
            </span>
          </span>
          <button
            type="button"
            className="shrink-0 text-xs text-muted-foreground underline-offset-4 hover:underline"
            onClick={() => {
              onPick(null)
              setQuery('')
            }}
          >
            Change
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="fund-search">Fund</Label>
      <Input
        id="fund-search"
        autoComplete="off"
        placeholder="Parag Parikh Flexi Cap"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      {settled.trim().length >= 3 && (
        <div className="max-h-56 overflow-y-auto rounded-md border">
          {isFetching && (
            <p className="px-3 py-2 text-xs text-muted-foreground">Searching AMFI…</p>
          )}
          {isError && (
            <p className="px-3 py-2 text-xs text-muted-foreground">
              AMFI&rsquo;s search is not answering. Try again in a moment.
            </p>
          )}
          {data && data.length === 0 && !isFetching && (
            <p className="px-3 py-2 text-xs text-muted-foreground">
              Nothing matched. Try the fund house name, or fewer words.
            </p>
          )}
          <ul className="divide-y">
            {(data ?? []).slice(0, 40).map((scheme) => (
              <li key={scheme.scheme_code}>
                <button
                  type="button"
                  className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left hover:bg-muted"
                  onClick={() => onPick(scheme)}
                >
                  <span className="text-sm leading-tight">{scheme.scheme_name}</span>
                  <span className="num text-xs text-muted-foreground">
                    AMFI {scheme.scheme_code}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        {/* Said plainly, because the choice is consequential and reversible only
            by deleting the holding. */}
        Pick the exact plan you hold — Direct and Regular are separate schemes
        with separate codes, and which one you own changes what this app tells
        you.
      </p>
    </div>
  )
}
