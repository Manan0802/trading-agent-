import { useState } from 'react'
import { ChevronRight } from 'lucide-react'

/**
 * A sentence anyone can read, with the arithmetic one click behind it.
 *
 * Written after Manan said he could not tell what the app was doing. Every
 * panel was leading with `t = +3.11` and `IC +0.073` — correct, checkable, and
 * addressed to a statistician rather than to the person deciding where to put
 * money.
 *
 * The numbers are not removed. Hiding them would make the app unfalsifiable,
 * which is the opposite of the point: the whole argument here is that claims
 * should be checkable. They move one click away, because you need them when
 * you are testing a claim and not while you are reading one.
 *
 * So: the sentence carries the meaning, the detail carries the proof.
 */
export function Plain({
  children,
  detail,
  label = 'the numbers',
}: {
  /** The sentence. Should make sense with the detail closed, always. */
  children: React.ReactNode
  /** The arithmetic behind it. */
  detail: React.ReactNode
  label?: string
}) {
  const [open, setOpen] = useState(false)

  return (
    <div className="flex flex-col gap-1.5">
      <p className="max-w-3xl text-sm">{children}</p>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        // A 12px line of text is a 16px-tall tap target, which is half of what
        // a thumb can reliably hit. `min-h-8` gives it the full 32px and the
        // negative margin gives the extra height back to the layout, so the
        // control grows without the page moving.
        className="-my-2 flex min-h-8 w-fit items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ChevronRight
          aria-hidden
          className={`size-3 transition-transform ${open ? 'rotate-90' : ''}`}
        />
        {open ? 'Hide' : 'Show'} {label}
      </button>
      {open && (
        <div className="max-w-3xl border-l-2 pl-3 text-xs text-muted-foreground">
          {detail}
        </div>
      )}
    </div>
  )
}
