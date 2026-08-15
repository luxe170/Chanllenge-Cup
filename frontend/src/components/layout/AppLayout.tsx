import {
  Bell,
  BookOpenCheck,
  ChartNoAxesCombined,
  ChevronLeft,
  ChevronRight,
  CircleUserRound,
  FileSearch,
  GitBranch,
  LayoutDashboard,
  Menu,
  Search,
  Sparkles,
  UserRoundSearch,
} from 'lucide-react'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { AppLink, useAppRouter } from '../../router'

const navigation = [
  { to: '/dashboard', label: '全局工作台', icon: LayoutDashboard },
  { to: '/graph', label: '岗位图谱', icon: GitBranch },
  { to: '/evolution', label: '岗位演化', icon: ChartNoAxesCombined },
  { to: '/resume', label: '简历解析', icon: FileSearch },
  { to: '/match', label: '匹配诊断', icon: UserRoundSearch },
  { to: '/review', label: '审核评测', icon: BookOpenCheck },
]

const pageTitles: Record<string, { eyebrow: string; title: string }> = {
  '/dashboard': { eyebrow: 'OVERVIEW', title: '全局工作台' },
  '/graph': { eyebrow: 'KNOWLEDGE GRAPH', title: '岗位能力图谱' },
  '/evolution': { eyebrow: 'EVOLUTION', title: '岗位动态演化' },
  '/resume': { eyebrow: 'RESUME PARSER', title: '简历能力解析' },
  '/match': { eyebrow: 'MATCHING', title: '人岗匹配诊断' },
  '/review': { eyebrow: 'QUALITY CENTER', title: '审核与评测' },
}

export default function AppLayout({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { path } = useAppRouter()
  const current = pageTitles[path] ?? pageTitles['/dashboard']

  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark"><Sparkles size={21} /></div>
          <div className="brand-copy">
            <strong>职涯棱镜</strong>
            <span>CAREER PRISM</span>
          </div>
        </div>
        <nav className="main-nav" aria-label="主导航">
          {navigation.map(({ to, label, icon: Icon }) => (
            <AppLink key={to} to={to} onClick={() => setMobileOpen(false)} className={path === to ? 'nav-item active' : 'nav-item'}>
              <Icon size={19} strokeWidth={1.8} />
              <span>{label}</span>
              {to === '/review' && <em>28</em>}
            </AppLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="system-status">
            <span className="status-pulse" />
            <div><strong>系统运行正常</strong><small>最近更新 2 分钟前</small></div>
          </div>
          <button className="collapse-button" onClick={() => setCollapsed((value) => !value)} aria-label="收起侧边栏">
            {collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}
          </button>
        </div>
      </aside>
      {mobileOpen && <button className="mobile-backdrop" onClick={() => setMobileOpen(false)} aria-label="关闭导航" />}
      <div className="main-column">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileOpen(true)} aria-label="打开导航"><Menu size={22} /></button>
          <div className="page-heading">
            <span>{current.eyebrow}</span>
            <h1>{current.title}</h1>
          </div>
          <div className="topbar-actions">
            <label className="global-search">
              <Search size={17} />
              <input placeholder="搜索岗位、技能或技术栈" />
              <kbd>⌘ K</kbd>
            </label>
            <button className="icon-button notification" aria-label="通知"><Bell size={19} /><i /></button>
            <button className="user-menu"><CircleUserRound size={22} /><span>评审演示</span></button>
          </div>
        </header>
        <main className="page-content">{children}</main>
      </div>
    </div>
  )
}
