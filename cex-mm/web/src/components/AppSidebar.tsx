import { NavLink, useLocation } from 'react-router-dom'
import {
  Activity,
  GitCompareArrows,
  LayoutDashboard,
  ListOrdered,
  Power,
  Scale,
  Wallet,
} from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/positions', label: 'Positions', icon: Wallet },
  { to: '/orders', label: 'Orders', icon: ListOrdered },
  { to: '/reconcile', label: 'Reconcile', icon: GitCompareArrows },
  { to: '/tca', label: 'TCA', icon: Activity },
  { to: '/control', label: 'Control', icon: Power },
] as const

export function AppSidebar() {
  const location = useLocation()

  return (
    <Sidebar collapsible="icon" variant="inset">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              className="data-[slot=sidebar-menu-button]:p-1.5!"
            >
              <NavLink to="/">
                <Scale className="size-5!" />
                <span className="text-base font-semibold">OEMS</span>
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV.map((item) => {
                const active =
                  'end' in item && item.end
                    ? location.pathname === item.to
                    : location.pathname === item.to ||
                      location.pathname.startsWith(`${item.to}/`)
                const Icon = item.icon
                return (
                  <SidebarMenuItem key={item.to}>
                    <SidebarMenuButton asChild isActive={active} tooltip={item.label}>
                      <NavLink to={item.to} end={'end' in item ? item.end : false}>
                        <Icon />
                        <span>{item.label}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
