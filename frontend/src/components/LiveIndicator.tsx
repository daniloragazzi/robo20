export function LiveIndicator({ connected }: { connected: boolean }) {
  if (!connected) return null;

  return (
    <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded bg-zinc-900/80 px-2 py-1">
      <span className="relative flex h-2.5 w-2.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-green-500" />
      </span>
      <span className="text-xs font-semibold text-green-400">LIVE</span>
    </div>
  );
}
