import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

const VendorSite = lazy(() => import('./pages/PublicSite/VendorSite'));

const Home = () => (
  <div className="flex min-h-screen items-center justify-center p-8 bg-[var(--color-surface-base)]">
    <div className="max-w-xl text-center">
      <h1 className="mb-3 text-4xl font-bold text-[var(--color-neutral-900)]">
        Study Abroad Platform
      </h1>
      <p className="text-[var(--color-neutral-500)]">
        Public vendor sites live at <code>/v/&lt;vendor-slug&gt;</code>. The vendor
        management console will live under <code>/vendors/&lt;id&gt;</code>.
      </p>
    </div>
  </div>
);

const App = () => (
  <Suspense fallback={null}>
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/v/:vendorSlug" element={<VendorSite />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </Suspense>
);

export default App;
