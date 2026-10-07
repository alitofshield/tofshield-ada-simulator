import type { getContainer } from "@cloudflare/containers";

export const TEAM_SHARE_ROOT = "TOFshield_Team_Share/HDF5/";
export const TEAM_SHARE_LIST_PATH = "/api/team-share/list";
export const TEAM_SHARE_OPEN_PATH = "/api/team-share/open";
export const TEAM_SHARE_INTERNAL_IMPORT_PATH =
  "/api/internal/team-share-import";

const HDF5_EXTENSION = /\.(?:h5|hdf5|hdf)$/i;
const ENCODED_TRAVERSAL = /%(?:2e|2f|5c)/i;
const CONTROL_CHARACTER = /[\u0000-\u001f\u007f]/;
const MAX_CURSOR_LENGTH = 4096;
const DEFAULT_LIST_LIMIT = 100;
const MAX_LIST_LIMIT = 200;
const MAX_OPEN_REQUEST_BYTES = 8192;

type TeamShareBucket = R2Bucket;
type TeamShareContainer = Pick<ReturnType<typeof getContainer>, "fetch">;
type TeamShareR2Object = R2Object;

interface ListedTeamShareObject {
  object: TeamShareR2Object;
  relativeKey: string;
}

export class TeamShareRequestError extends Error {
  constructor(
    message: string,
    readonly status = 400,
  ) {
    super(message);
    this.name = "TeamShareRequestError";
  }
}

export interface TeamShareFolderEntry {
  type: "folder";
  name: string;
  prefix: string;
}

export interface TeamShareFileEntry {
  type: "file";
  name: string;
  key: string;
  size: number;
  uploaded: string;
}

export interface TeamShareListResponse {
  prefix: string;
  folders: TeamShareFolderEntry[];
  files: TeamShareFileEntry[];
  truncated: boolean;
  cursor?: string;
}

function decodeForTraversalCheck(value: string): string {
  let decoded = value;

  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (ENCODED_TRAVERSAL.test(decoded)) {
      throw new TeamShareRequestError("Encoded path traversal is not allowed.");
    }

    try {
      const next = decodeURIComponent(decoded);
      if (next === decoded) {
        return decoded;
      }
      decoded = next;
    } catch {
      throw new TeamShareRequestError("Malformed path encoding.");
    }
  }

  if (decoded.includes("%")) {
    throw new TeamShareRequestError("Excessive path encoding is not allowed.");
  }

  return decoded;
}

function validateRelativePath(value: string, allowEmpty: boolean): string {
  if (typeof value !== "string") {
    throw new TeamShareRequestError("A Team Share path is required.");
  }

  const decoded = decodeForTraversalCheck(value);

  if (!decoded && allowEmpty) {
    return "";
  }

  if (!decoded) {
    throw new TeamShareRequestError("A Team Share file key is required.");
  }

  if (
    decoded.startsWith("/") ||
    decoded.startsWith("\\") ||
    decoded.includes("\\") ||
    decoded.startsWith(TEAM_SHARE_ROOT) ||
    CONTROL_CHARACTER.test(decoded)
  ) {
    throw new TeamShareRequestError("The Team Share path is not permitted.");
  }

  const segments = decoded.split("/");
  if (segments.some((segment) => segment === "" || segment === "." || segment === "..")) {
    throw new TeamShareRequestError("Path traversal is not allowed.");
  }

  return decoded;
}

function parseLimit(rawLimit: string | null): number {
  if (rawLimit === null || rawLimit === "") {
    return DEFAULT_LIST_LIMIT;
  }

  if (!/^\d+$/.test(rawLimit)) {
    throw new TeamShareRequestError("The listing limit must be an integer.");
  }

  const limit = Number(rawLimit);
  if (limit < 1 || limit > MAX_LIST_LIMIT) {
    throw new TeamShareRequestError(
      `The listing limit must be between 1 and ${MAX_LIST_LIMIT}.`,
    );
  }

  return limit;
}

function parseCursor(rawCursor: string | null): string | undefined {
  if (rawCursor === null || rawCursor === "") {
    return undefined;
  }

  if (
    rawCursor.length > MAX_CURSOR_LENGTH ||
    CONTROL_CHARACTER.test(rawCursor)
  ) {
    throw new TeamShareRequestError("The listing cursor is invalid.");
  }

  return rawCursor;
}

function relativeFromR2Key(key: string): string {
  if (!key.startsWith(TEAM_SHARE_ROOT)) {
    throw new TeamShareRequestError("R2 returned an object outside the allowed root.", 502);
  }

  return key.slice(TEAM_SHARE_ROOT.length);
}

function leafName(path: string): string {
  const parts = path.replace(/\/$/, "").split("/");
  return parts[parts.length - 1] ?? path;
}

function jsonResponse(payload: unknown, status = 200): Response {
  return Response.json(payload, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

export function teamShareErrorResponse(error: unknown): Response {
  if (error instanceof TeamShareRequestError) {
    return jsonResponse({ error: error.message }, error.status);
  }

  console.error("Team Share Worker error", error);
  return jsonResponse({ error: "Team Share request failed." }, 500);
}

export async function listTeamShareObjects(
  request: Request,
  bucket: TeamShareBucket,
): Promise<Response> {
  const url = new URL(request.url);
  const relativePrefix = validateRelativePath(
    url.searchParams.get("prefix") ?? "",
    true,
  );
  const folderPrefix = relativePrefix ? `${relativePrefix.replace(/\/$/, "")}/` : "";
  const cursor = parseCursor(url.searchParams.get("cursor"));
  const limit = parseLimit(url.searchParams.get("limit"));

  const listing = await bucket.list({
    prefix: `${TEAM_SHARE_ROOT}${folderPrefix}`,
    delimiter: "/",
    cursor,
    limit,
  });

  const folders = listing.delimitedPrefixes.map((r2Prefix: string) => {
    const relativePrefixValue = relativeFromR2Key(r2Prefix);
    return {
      type: "folder" as const,
      name: leafName(relativePrefixValue),
      prefix: relativePrefixValue.replace(/\/$/, ""),
    };
  });

  const files = listing.objects
    .map(
      (object: TeamShareR2Object): ListedTeamShareObject => ({
        object,
        relativeKey: relativeFromR2Key(object.key),
      }),
    )
    .filter((entry: ListedTeamShareObject) =>
      HDF5_EXTENSION.test(entry.relativeKey),
    )
    .map((entry: ListedTeamShareObject) => ({
      type: "file" as const,
      name: leafName(entry.relativeKey),
      key: entry.relativeKey,
      size: entry.object.size,
      uploaded: entry.object.uploaded.toISOString(),
    }));

  const response: TeamShareListResponse = {
    prefix: relativePrefix,
    folders,
    files,
    truncated: listing.truncated,
  };

  if (listing.truncated && listing.cursor) {
    response.cursor = listing.cursor;
  }

  return jsonResponse(response);
}

interface OpenTeamShareRequest {
  key?: unknown;
}

async function readOpenRequest(request: Request): Promise<string> {
  const contentLength = request.headers.get("Content-Length");
  if (contentLength !== null) {
    const parsedLength = Number(contentLength);
    if (!Number.isFinite(parsedLength) || parsedLength > MAX_OPEN_REQUEST_BYTES) {
      throw new TeamShareRequestError("The open request is too large.", 413);
    }
  }

  const contentType = request.headers.get("Content-Type") ?? "";
  if (!contentType.toLowerCase().startsWith("application/json")) {
    throw new TeamShareRequestError("Content-Type must be application/json.", 415);
  }

  let payload: OpenTeamShareRequest;
  try {
    payload = (await request.json()) as OpenTeamShareRequest;
  } catch {
    throw new TeamShareRequestError("The open request must contain valid JSON.");
  }

  if (typeof payload.key !== "string") {
    throw new TeamShareRequestError("A Team Share file key is required.");
  }

  return validateRelativePath(payload.key, false);
}

export async function openTeamShareObject(
  request: Request,
  bucket: TeamShareBucket,
  container: TeamShareContainer,
): Promise<Response> {
  const relativeKey = await readOpenRequest(request);
  if (!HDF5_EXTENSION.test(relativeKey)) {
    throw new TeamShareRequestError(
      "Only .h5, .hdf5, and .hdf files may be opened.",
      415,
    );
  }

  const r2Key = `${TEAM_SHARE_ROOT}${relativeKey}`;
  const object = await bucket.get(r2Key);
  if (object === null) {
    throw new TeamShareRequestError("The selected HDF5 object was not found.", 404);
  }

  const internalUrl = new URL(request.url);
  internalUrl.pathname = TEAM_SHARE_INTERNAL_IMPORT_PATH;
  internalUrl.search = "";
  internalUrl.hash = "";

  const headers = new Headers({
    "Content-Type": "application/octet-stream",
    "Content-Length": String(object.size),
    "X-ADA-Internal-Import": "team-share-worker",
    "X-ADA-Team-Share-Key": encodeURIComponent(relativeKey),
  });

  return container.fetch(
    new Request(internalUrl, {
      method: "POST",
      headers,
      body: object.body,
    }),
  );
}
