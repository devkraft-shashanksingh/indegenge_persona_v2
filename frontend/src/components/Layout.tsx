import { Outlet, Link, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { checkHealth } from '@/lib/api';
import {
  LayoutDashboard,
  PlayCircle,
  BarChart3,
  Activity,
  UserPlus,
  Users,
  Library,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  CheckCircle2,
  Network,
  BookOpen,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navigation = [
  {
    name: 'Dashboard',
    description: 'Overview & metrics',
    href: '/',
    icon: LayoutDashboard,
  },
  {
    name: 'Create Persona',
    description: 'Generate new personas',
    href: '/create-persona',
    icon: UserPlus,
  },
  {
    name: 'Persona Library',
    description: 'Browse & manage personas',
    href: '/personas',
    icon: Users,
  },
  {
    name: 'Brand Library',
    description: 'Brand knowledge & assets',
    href: '/brand-library',
    icon: Library,
  },
  {
    name: 'Evidence Bank',
    description: 'Verified facts & insights',
    href: '/knowledge-graph',
    icon: BookOpen,
  },
  {
    name: 'Simulation Hub',
    description: 'Run AI simulations',
    href: '/simulation',
    icon: PlayCircle,
  },
  {
    name: 'Analytics',
    description: 'Insights & reports',
    href: '/analytics',
    icon: BarChart3,
  },
];

const guidedFlow = [
  {
    title: 'Start with context',
    description: 'Scan the dashboard for recent engagement shifts.',
    href: '/',
  },
  {
    title: 'Generate & align personas',
    description: 'Create personas, then refine them with the builder.',
    href: '/create-persona',
  },
  {
    title: 'Persona Library',
    description: 'Manage and compare personas in the library.',
    href: '/personas',
  },
  {
    title: 'Run simulations',
    description: 'Test narratives and sequencing in Simulation Hub.',
    href: '/simulation',
  },
  {
    title: 'Share outcomes',
    description: 'Publish insights to Analytics for stakeholders.',
    href: '/analytics',
  },
];

export function Layout() {
  const location = useLocation();
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [personaCount, setPersonaCount] = useState<number | undefined>();
  const [isGuidedFlowOpen, setIsGuidedFlowOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await checkHealth();
      if (!cancelled) {
        setApiOk(res.ok);
        setPersonaCount(res.personas);
      }
    })();
    const interval = setInterval(async () => {
      const res = await checkHealth();
      if (!cancelled) {
        setApiOk(res.ok);
        setPersonaCount(res.personas);
      }
    }, 15000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  return (
    <div className="flex h-screen bg-background font-sans text-foreground">
      {/* Sidebar - Indegene Purple Design */}
      <aside className="w-64 bg-gradient-to-b from-[hsl(262,60%,38%)] to-[hsl(262,60%,32%)] flex flex-col hidden md:flex">
        {/* Logo Area - Indegene Branding */}
        <div className="px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Activity className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-white font-bold text-lg leading-tight">Indegene</h1>
              <h2 className="text-white/90 font-semibold text-sm leading-tight">PersonaSim</h2>
              <p className="text-white/60 text-xs">Healthcare Intelligence</p>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-1.5 text-white/60 text-xs">
            <Activity className="h-3 w-3" />
            <span>Powered by Indegene</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4 px-3">
          <div className="px-2 mb-3 text-[10px] font-semibold text-white/40 uppercase tracking-wider">
            Navigation
          </div>
          <div className="space-y-1">
            {navigation.map((item) => {
              // For Dashboard (href="/"), use exact match; for others, use startsWith
              const isActive = item.href === '/'
                ? location.pathname === item.href
                : location.pathname.startsWith(item.href);
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    'group flex items-center justify-between px-3 py-3 rounded-lg transition-all duration-200',
                    isActive
                      ? 'bg-primary text-white shadow-lg'
                      : 'text-white/70 hover:bg-white/10 hover:text-white'
                  )}
                >
                  <div className="flex items-center gap-3">
                    <item.icon
                      className={cn(
                        'h-5 w-5 flex-shrink-0 transition-colors',
                        isActive ? 'text-white' : 'text-white/70 group-hover:text-white'
                      )}
                    />
                    <div>
                      <span className="block text-sm font-medium">{item.name}</span>
                      <span className={cn(
                        "block text-xs",
                        isActive ? "text-white/80" : "text-white/50"
                      )}>
                        {item.description}
                      </span>
                    </div>
                  </div>
                  {isActive && (
                    <ChevronRight className="h-4 w-4 text-white/80" />
                  )}
                </Link>
              );
            })}
          </div>

          <div className="mt-6 mb-2 px-2 border-t border-white/10 pt-4">
            {/* Guided user flow */}
            <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-4 shadow-inner">
              <button
                onClick={() => setIsGuidedFlowOpen(!isGuidedFlowOpen)}
                className="w-full flex items-center justify-between gap-2 group cursor-pointer"
              >
                <div className="text-left">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-white/60 group-hover:text-white/80 transition-colors">Suggested flow</p>
                  {isGuidedFlowOpen && (
                    <>
                      <p className="text-sm font-medium text-white">Tell the persona story</p>
                      <p className="text-xs text-white/60">Step-by-step guide</p>
                    </>
                  )}
                </div>
                {isGuidedFlowOpen ? (
                  <ChevronDown className="h-4 w-4 text-white/40" />
                ) : (
                  <ChevronUp className="h-4 w-4 text-white/40" />
                )}
              </button>

              {isGuidedFlowOpen && (
                <div className="mt-4 space-y-2 animate-in fade-in slide-in-from-top-2 duration-200">
                  {guidedFlow.map((step, index) => (
                    <Link
                      to={step.href}
                      key={step.title}
                      className="group flex items-start gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-white/10"
                    >
                      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/10 text-[10px] font-semibold text-white">
                        {index + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold text-white truncate">{step.title}</p>
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300 opacity-0 transition-opacity group-hover:opacity-100" />
                        </div>
                        <p className="text-xs text-white/60 line-clamp-2">{step.description}</p>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        </nav>

        {/* Sidebar Footer - API Status */}
        <div className="p-4 border-t border-white/10">
          <div className="flex items-center gap-2">
            <div className={cn(
              "w-2 h-2 rounded-full",
              apiOk ? "bg-emerald-400" : "bg-red-400"
            )} />
            <span className="text-white/90 text-sm font-medium">API {apiOk ? 'Online' : 'Offline'}</span>
          </div>
          <p className="text-white/50 text-xs mt-1">
            relative • {personaCount ?? 0} personas
          </p>
          <p className="text-white/40 text-[10px] mt-3">
            Enabling healthcare organizations<br />to be future ready
          </p>
        </div>
      </aside>

      {/* Main Content Wrapper */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Main Content Area - No top header for cleaner look */}
        <main className="flex-1 overflow-y-auto bg-background">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
