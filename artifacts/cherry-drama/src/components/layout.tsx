import { Link, useLocation } from "wouter";
import { LayoutDashboard, Settings, Library, PlaySquare } from "lucide-react";
import { useGetJobStats } from "@workspace/api-client-react";
import { ReactNode } from "react";
import logo from "/cherry-drama-logo.jpg";

export function Layout({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  const { data: stats } = useGetJobStats();

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-sidebar flex flex-col justify-between">
        <div>
          <div className="h-16 flex items-center px-6 border-b border-border">
            <img src={logo} alt="Cherry Drama" className="h-8 w-8 rounded-md mr-3 object-cover" />
            <span className="font-bold text-lg tracking-tight text-white">Cherry Drama</span>
          </div>
          
          <nav className="p-4 space-y-1">
            <Link href="/" className={`flex items-center px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${location === "/" ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"}`}>
              <PlaySquare className="mr-3 h-4 w-4" />
              Upload & Recap
            </Link>
            
            <Link href="/processing" className={`flex items-center px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${location === "/processing" ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"}`}>
              <LayoutDashboard className="mr-3 h-4 w-4" />
              Processing Queue
              {stats && stats.processing > 0 && (
                <span className="ml-auto bg-primary text-primary-foreground text-xs py-0.5 px-2 rounded-full font-bold">
                  {stats.processing}
                </span>
              )}
            </Link>
            
            <Link href="/library" className={`flex items-center px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${location === "/library" ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"}`}>
              <Library className="mr-3 h-4 w-4" />
              Recap Library
            </Link>
          </nav>
        </div>
        
        <div className="p-4">
          <div className="mb-4 px-3 py-3 bg-card rounded-md border border-card-border">
            <div className="text-xs text-muted-foreground mb-1 uppercase tracking-wider font-semibold">Channel Stats</div>
            <div className="flex justify-between items-end">
              <div className="text-2xl font-bold">{stats?.completed || 0}</div>
              <div className="text-xs text-muted-foreground mb-1">completed recaps</div>
            </div>
          </div>
          
          <Link href="/settings" className={`flex items-center px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${location === "/settings" ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"}`}>
            <Settings className="mr-3 h-4 w-4" />
            Settings
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto relative">
        <div className="absolute inset-0 bg-gradient-to-br from-background to-[#2a0f18] opacity-50 pointer-events-none" />
        <div className="relative h-full flex flex-col z-10">
          {children}
        </div>
      </main>
    </div>
  );
}