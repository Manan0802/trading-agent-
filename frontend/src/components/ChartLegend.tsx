/**
 * The legend, deliberately outside the chart.
 *
 * The SVG is `aria-hidden` — every tick and label inside it is decoration whose
 * meaning is repeated in text — and a legend rendered by Recharts would be
 * hidden along with it. Line style, not just colour, is what separates the two
 * series, so the swatch draws the dash pattern rather than a colour chip.
 */
export function ChartLegend({
  series,
}: {
  series: { label: string; color: string; dashed?: boolean }[]
}) {
  return (
    <ul className="flex flex-wrap items-center gap-x-5 gap-y-1.5">
      {series.map((s) => (
        <li key={s.label} className="flex items-center gap-2">
          <svg aria-hidden width="22" height="8" viewBox="0 0 22 8" className="shrink-0">
            <line
              x1="0"
              y1="4"
              x2="22"
              y2="4"
              stroke={s.color}
              strokeWidth="2"
              strokeDasharray={s.dashed ? '5 3' : undefined}
            />
          </svg>
          <span className="text-xs text-muted-foreground">{s.label}</span>
        </li>
      ))}
    </ul>
  )
}
