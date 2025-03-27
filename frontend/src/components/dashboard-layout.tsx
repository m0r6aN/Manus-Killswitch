// app/components/dashboard-layout.tsx

"use client"

import type React from "react"

import { useState, useEffect } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { BarChart3, Home, MessageSquare, Settings, Users, Activity, BrainCircuit } from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarTrigger,
  SidebarHeader,
  SidebarSeparator,
  SidebarProvider,
} from "@/components/ui/sidebar"
import { ModeToggle } from "@/components/mode-toggle"
import { ConnectionStatusWrapper } from "@/components/connection-status-wrapper"
import { useWebSocket } from "@/contexts/websocket-context"

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const [mounted, setMounted] = useState(false)
  const { isConnected, error } = useWebSocket()
  console.log("Rendering DashboardLayout, isConnected:", isConnected);

  // Prevent hydration mismatch
  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return null
  }

  return (
    <SidebarProvider>
      <div className="flex min-h-screen">
        <Sidebar>
          <SidebarHeader>
            <div className="flex items-center gap-2 px-2">
              <BrainCircuit className="h-6 w-6" />
              <span className="font-semibold">AI Council</span>
            </div>
          </SidebarHeader>
          <SidebarSeparator />
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel>Navigation</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild isActive={pathname === "/"} tooltip="Home">
                      <Link href="/">
                        <Home className="h-4 w-4" />
                        <span>Home</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild isActive={pathname === "/debates"} tooltip="Debates">
                      <Link href="/debates">
                        <MessageSquare className="h-4 w-4" />
                        <span>Debates</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild isActive={pathname === "/analytics"} tooltip="Analytics">
                      <Link href="/analytics">
                        <BarChart3 className="h-4 w-4" />
                        <span>Analytics</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild isActive={pathname === "/agents"} tooltip="Agents">
                      <Link href="/agents">
                        <Users className="h-4 w-4" />
                        <span>Agents</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
            <SidebarSeparator />
            <SidebarGroup>
              <SidebarGroupLabel>System</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild isActive={pathname === "/settings"} tooltip="Settings">
                      <Link href="/settings">
                        <Settings className="h-4 w-4" />
                        <span>Settings</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
          <SidebarFooter>
            <div className="p-2">
              <div className="rounded-lg bg-muted p-2 text-xs">
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-muted-foreground" />
                  <span className="text-muted-foreground">AI Council v1.0</span>
                </div>
              </div>
            </div>
          </SidebarFooter>
        </Sidebar>
        <div className="flex-1">
          <header className="sticky top-0 z-10 flex h-16 items-center gap-4 border-b bg-background px-6">
            <SidebarTrigger />
            <div className="flex-1" />
            <ConnectionStatusWrapper />
            <ModeToggle />
          </header>
          <main className="flex-1 p-6">
            {error ? (
              <div className="text-red-500">Error: {error.message}. Please check your WebSocket connection.</div>
            ) : !isConnected ? (
              <div>Connecting to WebSocket...</div>
            ) : (
              children
            )}
          </main>
        </div>
      </div>
    </SidebarProvider>
  )
}

