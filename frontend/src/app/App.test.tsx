import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";

afterEach(() => vi.unstubAllGlobals());

function healthyFetch(mongo = "up", neo = "up") {
  return vi.fn((url: string) =>
    Promise.resolve(
      new Response(
        JSON.stringify(
          url.endsWith("/live")
            ? { status: "alive" }
            : {
                status: mongo === "up" && neo === "up" ? "ready" : "not_ready",
                dependencies: { mongodb: mongo, neo4j: neo },
              },
        ),
        {
          status:
            url.endsWith("/ready") && (mongo === "down" || neo === "down")
              ? 503
              : 200,
        },
      ),
    ),
  );
}

it("renders accessible loading state", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise(() => {})),
  );
  render(<App />);
  expect(
    screen.getByRole("heading", { name: /Evidence first/ }),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("status")[0]).toHaveTextContent("Checking");
  expect(screen.getByRole("button", { name: /Refresh/ })).toBeDisabled();
});
it("displays successful connectivity and refreshes", async () => {
  const fetcher = healthyFetch();
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  expect(
    await screen.findByText("All foundation services are available."),
  ).toBeInTheDocument();
  expect(screen.getAllByText("Available")).toHaveLength(3);
  fireEvent.click(screen.getByRole("button", { name: /Refresh/ }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(5));
});
it("distinguishes dependency outage from backend outage", async () => {
  vi.stubGlobal("fetch", healthyFetch("up", "down"));
  render(<App />);
  expect(await screen.findByText(/The backend is alive/)).toBeInTheDocument();
  expect(screen.getAllByText("Available")).toHaveLength(2);
  expect(screen.getByText("Unavailable")).toBeInTheDocument();
});
it("shows unreachable backend and unknown dependency state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new TypeError("private-network-error")),
  );
  render(<App />);
  expect(
    await screen.findByText("The backend could not be reached."),
  ).toBeInTheDocument();
  expect(screen.getAllByText("Unknown")).toHaveLength(2);
  expect(screen.queryByText(/private-network-error/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Refresh/ })).toBeEnabled();
});
