const CardSkeleton = () => (
  <div className="bg-white dark:bg-neutral-800 rounded-2xl border border-neutral-200 dark:border-white/10 p-6 shadow-sm">
    <div className="space-y-3">
      <div className="h-6 w-2/5 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
      <div className="h-12 w-3/5 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
      <div className="flex gap-2 mt-4">
        <div className="h-6 w-20 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
      </div>
    </div>
  </div>
);

export default CardSkeleton;
