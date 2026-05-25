interface Props {
  rows?: number;
  columns?: number;
}

const TableSkeleton = ({ rows = 8, columns = 5 }: Props) => (
  <div className="w-full">
    {/* Header row */}
    <div className="flex gap-2 mb-1">
      {Array.from({ length: columns }).map((_, i) => (
        <div
          key={i}
          className="flex-1 h-10 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse"
        />
      ))}
    </div>

    {/* Data rows */}
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="flex gap-2 mb-1">
        {Array.from({ length: columns }).map((_, j) => (
          <div
            key={j}
            className="flex-1 h-[52px] bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse"
          />
        ))}
      </div>
    ))}
  </div>
);

export default TableSkeleton;
