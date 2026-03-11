import * as React from "react"
import { ChevronDown } from "lucide-react"
import { cn } from "../../lib/utils"

/**
 * Custom Select wrapper — replaces native `<select>` with consistent
 * chevron positioning and padding across all browsers / themes.
 *
 * Usage:
 *   <Select value={v} onChange={fn} className="..." style={{...}}>
 *     <option>...</option>
 *   </Select>
 *
 * `className` and `style` are applied to the outer wrapper so layout
 * classes (flex-1, min-w-0, etc.) work correctly in flex contexts.
 */
const Select = React.forwardRef(
  ({ className, children, style, ...props }, ref) => {
    return (
      <div className={cn("relative", className)}>
        <select
          ref={ref}
          className="w-full appearance-none rounded-md py-2 pl-3 pr-9 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-50"
          style={{
            backgroundColor: "var(--color-bg-card)",
            border: "1px solid var(--color-border-muted)",
            color: "var(--color-text-primary)",
            ...style,
          }}
          {...props}
        >
          {children}
        </select>
        <ChevronDown
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4"
          style={{ color: "var(--color-text-tertiary)" }}
        />
      </div>
    )
  }
)
Select.displayName = "Select"

export { Select }
