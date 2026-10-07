import { Container, getContainer } from "@cloudflare/containers";

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
    return container.fetch(request);
  },
};
