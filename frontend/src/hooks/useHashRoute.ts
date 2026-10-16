import { useEffect, useState } from "react";

export const ROUTES = ["dashboard", "monitor", "graphs", "diagnostics", "logs"] as const;
export type Route = (typeof ROUTES)[number];

function parse(hash: string): Route {
  const name = hash.replace(/^#\/?/, "");
  return (ROUTES as readonly string[]).includes(name) ? (name as Route) : "dashboard";
}

// Minimal hash routing (#/monitor, #/graphs): enough for a few pages without
// pulling in a router library, and links survive reloads.
export function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash));

  useEffect(() => {
    const onChange = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return route;
}
