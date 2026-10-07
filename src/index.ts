import { Container, getContainer } from "@cloudflare/containers";
import {
  TEAM_SHARE_INTERNAL_IMPORT_PATH,
  TEAM_SHARE_LIST_PATH,
  TEAM_SHARE_OPEN_PATH,
  listTeamShareObjects,
  openTeamShareObject,
  teamShareErrorResponse,
} from "./team-share";

export class SimulatorContainer extends Container<Env> {
  defaultPort = 8080;
  sleepAfter = "10m";

  override onStart() {
    console.log("TOFshield simulator container started");
  }

  override onStop() {
    console.log("TOFshield simulator container stopped");
  }

  override onError(error: unknown) {
    console.error("TOFshield simulator container error", error);
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const container = getContainer(env.SIMULATOR_CONTAINER, "primary");
    const url = new URL(request.url);

    if (url.pathname === TEAM_SHARE_INTERNAL_IMPORT_PATH) {
      return new Response("Not found", { status: 404 });
    }

    try {
      if (url.pathname === TEAM_SHARE_LIST_PATH) {
        if (request.method !== "GET") {
          return new Response("Method not allowed", {
            status: 405,
            headers: { Allow: "GET" },
          });
        }
        return await listTeamShareObjects(request, env.TEAM_SHARE);
      }

      if (url.pathname === TEAM_SHARE_OPEN_PATH) {
        if (request.method !== "POST") {
          return new Response("Method not allowed", {
            status: 405,
            headers: { Allow: "POST" },
          });
        }
        return await openTeamShareObject(request, env.TEAM_SHARE, container);
      }
    } catch (error) {
      return teamShareErrorResponse(error);
    }

    return container.fetch(request);
  },
};
