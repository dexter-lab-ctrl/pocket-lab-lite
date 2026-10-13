/** Stable severity sort with same-underlying-issue deduplication; unknown never implies healthy. */
const priority = { danger: 0, review: 1, unknown: 2, neutral: 3 };
const alias = { runtime: 'runtime', control_api: 'control_api', worker_execution: 'worker_execution',
  command_bus: 'command_bus' };
export function prioritizeWorkspaceAttention(areas) {
  const seen = new Set();
  return (Array.isArray(areas) ? areas : []).filter((item) => item && item.tone !== 'ready')
    .map((item, index) => ({ item, index }))
    .sort((a, b) => (priority[a.item.tone] ?? 3) - (priority[b.item.tone] ?? 3) || a.index - b.index)
    .map(({ item }) => item)
    .filter((item) => {
      const issue = alias[item.key] || item.key || item.label;
      if (seen.has(issue)) return false;
      seen.add(issue); return true;
    });
}
