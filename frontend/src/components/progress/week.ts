// ISO-week helpers shared by the Progress charts and KPI row.
// Weeks start on Monday. All functions operate on local time.

/** The Monday (00:00 local) of the ISO week containing `date`. */
export function weekStartOf(date: Date): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const dow = (d.getDay() + 6) % 7 // 0 = Monday .. 6 = Sunday
  d.setDate(d.getDate() - dow)
  return d
}

/** Stable key (YYYY-MM-DD of the week's Monday) for bucketing by ISO week. */
export function weekKey(isoDate: string): string {
  const monday = weekStartOf(new Date(isoDate))
  const y = monday.getFullYear()
  const m = String(monday.getMonth() + 1).padStart(2, '0')
  const day = String(monday.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** True when `isoDate` falls in the same ISO week as `ref` (default: now). */
export function isSameWeek(isoDate: string, ref: Date = new Date()): boolean {
  return weekKey(isoDate) === weekKey(ref.toISOString())
}
