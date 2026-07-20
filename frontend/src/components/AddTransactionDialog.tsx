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
import { formatInr } from '@/lib/format'
import { addTransaction, type HoldingSummary } from '@/lib/portfolio-api'

const today = () => new Date().toISOString().slice(0, 10)

export function AddTransactionDialog({ holding }: { holding: HoldingSummary }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [txnType, setTxnType] = useState<'BUY' | 'SELL'>('BUY')
  const [txnDate, setTxnDate] = useState(today())
  const [units, setUnits] = useState('')
  const [price, setPrice] = useState('')
  const [error, setError] = useState<string | null>(null)

  const amount = Number(units) * Number(price)

  const add = useMutation({
    mutationFn: () =>
      addTransaction(holding.holding_id, {
        txn_date: txnDate,
        txn_type: txnType,
        units: Number(units),
        price: Number(price),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] })
      queryClient.invalidateQueries({ queryKey: ['benchmark'] })
      setUnits('')
      setPrice('')
      setError(null)
      setOpen(false)
    },
    onError: (err: any) =>
      setError(err.response?.data?.detail ?? 'Could not record this transaction.'),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="outline" size="xs">
            Add txn
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{holding.name}</DialogTitle>
          <DialogDescription>
            Record a purchase or redemption. Every SIP instalment is its own entry.
          </DialogDescription>
        </DialogHeader>

        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            add.mutate()
          }}
        >
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="txn_type">Type</Label>
              <Select
                value={txnType}
                onValueChange={(v) => setTxnType(v as 'BUY' | 'SELL')}
              >
                <SelectTrigger id="txn_type" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="BUY">Buy</SelectItem>
                  <SelectItem value="SELL">Sell</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="txn_date">Date</Label>
              <Input
                id="txn_date"
                type="date"
                required
                value={txnDate}
                onChange={(e) => setTxnDate(e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="units">Units</Label>
              <Input
                id="units"
                type="number"
                step="any"
                min="0.001"
                required
                value={units}
                onChange={(e) => setUnits(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="price">
                {holding.asset_type === 'MF' ? 'NAV' : 'Price'} per unit
              </Label>
              <Input
                id="price"
                type="number"
                step="any"
                min="0.001"
                required
                value={price}
                onChange={(e) => setPrice(e.target.value)}
              />
            </div>
          </div>

          {amount > 0 && (
            <p className="text-sm text-muted-foreground">
              Amount: <span className="font-medium text-foreground">{formatInr(amount)}</span>
            </p>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}

          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button">Cancel</Button>} />
            <Button type="submit" disabled={add.isPending}>
              {add.isPending ? 'Saving…' : 'Record'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
