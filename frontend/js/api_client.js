/**
 * FlowSplit API Client
 * Centralized HTTP communication with FastAPI backend.
 * Operates strictly in online mode with dynamic API configuration from .env.
 */

const ApiClient = {
  baseUrl: window.location.origin,

  async getPublicConfig() {
    try {
      const res = await fetch(`${this.baseUrl}/api/config/public`);
      if (!res.ok) throw new Error(`Config fetch failed: ${res.statusText}`);
      const cfg = await res.json();
      if (cfg.api_base_url && cfg.api_base_url.startsWith('http')) {
        this.baseUrl = cfg.api_base_url;
      }
      return cfg;
    } catch (err) {
      console.warn("Public config fetch failed:", err);
      return {
        google_maps_browser_key: null,
        google_maps_js_api_url: "https://maps.googleapis.com/maps/api/js",
        google_routes_api_url: "https://routes.googleapis.com/directions/v2:computeRoutes",
        has_routes_backend_key: false,
        has_street_view_backend_key: false,
        has_gemini_backend_key: false,
        online_mode_only: true,
        demo_mode_active: false,
      };
    }
  },

  async getCandidateRoutes(origin, destination, vehicleType = "passenger_car") {
    const payload = {
      origin: origin,
      destination: destination,
      vehicle_type: vehicleType,
    };
    const res = await fetch(`${this.baseUrl}/api/routes/candidates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Google Routes online fetch failed (${res.status})`);
    }
    return await res.json();
  },

  async analyzeRoutes(candidates, vehicleType = "passenger_car") {
    const payload = {
      candidates: candidates,
      vehicle_type: vehicleType,
      sample_interval_meters: 100.0,
    };
    const res = await fetch(`${this.baseUrl}/api/routes/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Route visual analysis failed (${res.status})`);
    }
    return await res.json();
  },

  async selectBestRoute(candidates, currentRouteId = null, vehicleType = "passenger_car") {
    const payload = {
      candidates: candidates,
      current_route_id: currentRouteId,
      vehicle_type: vehicleType,
    };
    const res = await fetch(`${this.baseUrl}/api/routes/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Route selection failed (${res.status})`);
    }
    return await res.json();
  },

  async runSimulation(totalTrips = 900, candidates = null) {
    const payload = {
      total_hourly_trips: totalTrips,
      candidates: candidates && candidates.length > 0 ? candidates : null,
    };
    const res = await fetch(`${this.baseUrl}/api/simulation/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Simulation run failed (${res.status})`);
    }
    return await res.json();
  },
};
