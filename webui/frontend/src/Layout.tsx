import { Outlet, NavLink } from "react-router-dom";
import { LayoutDashboard, List, Boxes, FileText, GitCompare } from "lucide-react";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/runs", label: "Runs", icon: List },
  { to: "/adapters", label: "Adapters", icon: Boxes },
  { to: "/fixtures", label: "Fixtures", icon: FileText },
  { to: "/compare", label: "Compare", icon: GitCompare },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <nav className="w-56 border-r border-gray-200 bg-white flex flex-col">
        <div className="px-4 py-5 border-b border-gray-200">
          <h1 className="text-sm font-bold text-gray-900">eval-pdf-extract</h1>
          <p className="text-xs text-gray-500 mt-0.5">Benchmark WebUI</p>
        </div>
        <ul className="flex-1 py-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
                    isActive
                      ? "bg-blue-50 text-blue-700 font-medium"
                      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
