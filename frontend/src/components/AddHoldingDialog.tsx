import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { FundPicker, type PickedScheme } from '@/components/FundPicker'
import {
  PORTFOLIO_QUERY_KEYS,
  createHolding,
  type AssetType,
} from '@/lib/portfolio-api'

export function AddHoldingDialog() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [assetType, setAssetType] = useState<AssetType>('MF')
  const [name, setName] = useState('')
  const [identifier, setIdentifier] = useState('')
  // A fund is chosen from AMFI rather than typed, so its name and code cannot
  // disagree. A stock is still typed: NSE tickers are short, printed on every
  // statement, and we have no search behind them.
  const [scheme, setScheme] = useState<PickedScheme | null>(null)

  const isMF = assetType === 'MF'
  const finalName = isMF ? scheme?.scheme_name ?? '' : name
  const finalIdentifier = isMF ? scheme?.scheme_code ?? '' : identifier.trim()
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setName('')
    setIdentifier('')
    setScheme(null)
  }

  const create = useMutation({
    mutationFn: () =>
      createHolding({
        name: finalName,
        asset_type: assetType,
        identifier: finalIdentifier,
      }),
    onSuccess: () => {
      for (const key of PORTFOLIO_QUERY_KEYS) {
        queryClient.invalidateQueries({ queryKey: [key] })
      }
      reset()
      setError(null)
      setOpen(false)
    },
    onError: (err: any) =>
      setError(err.response?.data?.detail ?? 'Could not add this holding.'),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm">Add holding</Button>} />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add a holding</DialogTitle>
          <DialogDescription>
            Something you already own. You'll add the purchases next.
          </DialogDescription>
        </DialogHeader>

        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            create.mutate()
          }}
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset_type">Type</Label>
            <Select
              value={assetType}
              onValueChange={(v) => {
                setAssetType(v as AssetType)
                reset()
              }}
            >
              <SelectTrigger id="asset_type" className="w-full">
                {/* Rendered explicitly: the bare value showed the raw code
                    "MF" in the closed trigger instead of "Mutual fund". */}
                <SelectValue>
                  {(value) => (value === 'STOCK' ? 'Stock' : 'Mutual fund')}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="MF">Mutual fund</SelectItem>
                <SelectItem value="STOCK">Stock</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {isMF ? (
            <FundPicker picked={scheme} onPick={setScheme} />
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  required
                  placeholder="Reliance Industries"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="identifier">NSE ticker</Label>
                <Input
                  id="identifier"
                  required
                  placeholder="RELIANCE.NS"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  NSE tickers end in .NS, which is what we fetch the live price
                  with.
                </p>
              </div>
            </>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}

          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button">Cancel</Button>} />
            <Button
              type="submit"
              disabled={create.isPending || !finalName || !finalIdentifier}
            >
              {create.isPending ? 'Adding…' : 'Add holding'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
