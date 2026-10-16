export type DiffOp = { type: "equal" | "removed" | "added"; text: string };

/** Unidades do diff: uma frase ou título por item. */
export const toUnits = (text: string) =>
  text
    .split(/\n+/)
    .flatMap((line) => line.match(/[^.!?…]+(?:[.!?…]+|$)/g) ?? [])
    .map((s) => s.trim())
    .filter(Boolean);

/** Diff por frase via LCS (textos curtos: O(n·m) é suficiente). */
export function diffUnits(before: string[], after: string[]): DiffOp[] {
  const n = before.length;
  const m = after.length;
  const lcs = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      lcs[i][j] = before[i] === after[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
  const ops: DiffOp[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (before[i] === after[j]) {
      ops.push({ type: "equal", text: before[i] });
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) ops.push({ type: "removed", text: before[i++] });
    else ops.push({ type: "added", text: after[j++] });
  }
  while (i < n) ops.push({ type: "removed", text: before[i++] });
  while (j < m) ops.push({ type: "added", text: after[j++] });
  return ops;
}
