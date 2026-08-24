import type { LucideIcon } from 'lucide-react'
import { ArrowDownRight, ArrowUpRight, X } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Trend } from '../types'

export function SectionHeader({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="section-header">
      <div>
        {eyebrow && <span className="section-eyebrow">{eyebrow}</span>}
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="section-action">{action}</div>}
    </div>
  )
}

export function MetricCard({ icon: Icon, label, value, suffix, change, tone = 'cyan' }: { icon: LucideIcon; label: string; value: string | number; suffix?: string; change?: string; tone?: 'cyan' | 'violet' | 'green' | 'amber' }) {
  const isDown = change?.startsWith('-')
  return (
    <article className={`metric-card tone-${tone}`}>
      <div className="metric-card-top"><span className="metric-icon"><Icon size={19} /></span><span className="metric-label">{label}</span></div>
      <div className="metric-value">{value}<small>{suffix}</small></div>
      {change && <div className={`metric-change ${isDown ? 'down' : ''}`}>{isDown ? <ArrowDownRight size={14} /> : <ArrowUpRight size={14} />}{change}<span>较上周期</span></div>}
    </article>
  )
}

const trendLabels: Record<Trend, string> = { new: '新增', rising: '上升', stable: '稳定', declining: '下降' }

export function TrendBadge({ trend }: { trend: Trend }) {
  return <span className={`trend-badge trend-${trend}`}>{trendLabels[trend]}</span>
}

export function Confidence({ value }: { value: number }) {
  return (
    <div className="confidence">
      <div className="confidence-track"><span style={{ width: `${value * 100}%` }} /></div>
      <strong>{Math.round(value * 100)}%</strong>
    </div>
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="modal-close" onClick={onClose} aria-label="关闭"><X size={17} /></button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}
