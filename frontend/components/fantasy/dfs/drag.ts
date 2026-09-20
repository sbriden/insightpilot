export const DFS_PLAYER_MIME = "application/x-dfs-player";

export type DfsDragSource = "pool" | "lineup";

export interface DfsDragPayload {
  playerId: string;
  source: DfsDragSource;
}

export function setDfsDragData(
  dataTransfer: DataTransfer,
  payload: DfsDragPayload
) {
  dataTransfer.effectAllowed =
    payload.source === "lineup" ? "move" : "copyMove";
  dataTransfer.setData(
    DFS_PLAYER_MIME,
    JSON.stringify(payload)
  );
  // Fallback for environments that strip custom MIME types.
  dataTransfer.setData("text/plain", payload.playerId);
}

export function readDfsDragData(
  dataTransfer: DataTransfer
): DfsDragPayload | null {
  const raw = dataTransfer.getData(DFS_PLAYER_MIME);
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as DfsDragPayload;
      if (parsed?.playerId) {
        return parsed;
      }
    } catch {
      // fall through
    }
  }
  const playerId = dataTransfer.getData("text/plain").trim();
  if (!playerId) {
    return null;
  }
  return { playerId, source: "pool" };
}
