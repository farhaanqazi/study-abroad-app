import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

const VendorSite = lazy(() => import('./pages/PublicSite/VendorSite'));
const RequireAuth = lazy(() => import('./pages/Console/RequireAuth'));
const ConsoleHome = lazy(() => import('./pages/Console/ConsoleHome'));
const ConsoleLayout = lazy(() => import('./pages/Console/ConsoleLayout'));
const LeadsDashboard = lazy(() => import('./pages/Console/LeadsDashboard'));
const CostSettingsPage = lazy(() => import('./pages/Console/CostSettingsPage'));
const SiteEditorPage = lazy(() => import('./pages/Console/SiteEditorPage'));

// Platform back-office admin console
const RequirePlatformAdmin = lazy(() => import('./pages/Admin/RequirePlatformAdmin'));
const AdminLayout = lazy(() => import('./pages/Admin/AdminLayout'));
const AdminOverview = lazy(() => import('./pages/Admin/AdminOverview'));
const WorkspaceRequestsQueue = lazy(() => import('./pages/Admin/WorkspaceRequestsQueue'));
const VendorsList = lazy(() => import('./pages/Admin/VendorsList'));
const VendorDetail = lazy(() => import('./pages/Admin/VendorDetail'));
const UsersList = lazy(() => import('./pages/Admin/UsersList'));
const AuditLogViewer = lazy(() => import('./pages/Admin/AuditLogViewer'));
const SupportTickets = lazy(() => import('./pages/Admin/SupportTickets'));

const Home = () => (
  <div className="flex min-h-screen items-center justify-center p-8 bg-[var(--color-surface-base)]">
    <div className="max-w-xl text-center">
      <h1 className="mb-3 text-4xl font-bold text-[var(--color-neutral-900)]">
        Study Abroad Platform
      </h1>
      <p className="text-[var(--color-neutral-500)]">
        Public vendor sites live at <code>/v/&lt;vendor-slug&gt;</code>. The vendor
        management console lives at <code>/console</code>.
      </p>
    </div>
  </div>
);

const App = () => (
  <Suspense fallback={null}>
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/v/:vendorSlug" element={<VendorSite />} />

      {/* Authenticated management console */}
      <Route
        path="/console"
        element={
          <RequireAuth>
            <ConsoleHome />
          </RequireAuth>
        }
      />
      <Route
        path="/console/:vendorId"
        element={
          <RequireAuth>
            <ConsoleLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="site" replace />} />
        <Route path="site" element={<SiteEditorPage />} />
        <Route path="leads" element={<LeadsDashboard />} />
        <Route path="cost-settings" element={<CostSettingsPage />} />
      </Route>

      {/* Platform back-office admin console */}
      <Route
        path="/admin"
        element={
          <RequirePlatformAdmin>
            <AdminLayout />
          </RequirePlatformAdmin>
        }
      >
        <Route index element={<AdminOverview />} />
        <Route path="requests" element={<WorkspaceRequestsQueue />} />
        <Route path="vendors" element={<VendorsList />} />
        <Route path="vendors/:vendorId" element={<VendorDetail />} />
        <Route path="users" element={<UsersList />} />
        <Route path="audit" element={<AuditLogViewer />} />
        <Route path="support" element={<SupportTickets />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </Suspense>
);

export default App;
