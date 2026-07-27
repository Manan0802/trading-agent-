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
import { createHolding, type AssetType } from '@/lib/portfolio-api'

export function AddHoldingDialog() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [assetType, setAssetType] = useState<AssetType>('MF')
  const [name, setName] = useState('')
  const [identifier, setIdentifier] = useState('')
  const [error, setError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () =>
      createHolding({ name, asset_type: assetType, identifier: identifier.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] })
      setName('')
      setIdentifier('')
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
              onValueChange={(v) => setAssetType(v as AssetType)}
            >
              <SelectTrigger id="asset_type" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="MF">Mutual fund</SelectItem>
                <SelectItem value="STOCK">Stock</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              required
              placeholder={
                assetType === 'MF'
                  ? 'Parag Parikh Flexi Cap Direct Growth'
                  : 'Reliance Industries'
              }
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="identifier">
              {assetType === 'MF' ? 'AMFI scheme code' : 'NSE ticker'}
            </Label>
            <Input
              id="identifier"
              required
              placeholder={assetType === 'MF' ? '122639' : 'RELIANCE.NS'}
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              {assetType === 'MF'
                ? 'This is what we fetch the daily NAV with.'
                : 'NSE tickers end in .NS, which is what we fetch the live price with.'}
            </p>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button">Cancel</Button>} />
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Adding…' : 'Add holding'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
