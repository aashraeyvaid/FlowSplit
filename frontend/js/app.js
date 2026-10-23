/**
 * FlowSplit Main Application Controller
 * Orchestrates online map rendering, real-time route evaluation, user geolocation, and UI states.
 * Operates strictly in online mode with all endpoints and credentials loaded from .env.
 */

class FlowSplitApp {
  constructor() {
    this.mapController = new MapController('flowsplitMap');
    this.candidates = [];
    this.selectedRouteId = null;
    this.currentDecision = null;
    this.config = null;
  }

  async init() {
    console.log("Initializing FlowSplit Online Application...");
    window.flowsplitApp = this;

    // 1. Fetch public backend configuration
    this.config = await ApiClient.getPublicConfig();
    this.updateConfigStatusUI();

    // 2. Initialize Map Engine
    await this.mapController.init(
      this.config.google_maps_browser_key,
      this.config.google_maps_js_api_url
    );
    this.mapController.onRouteSelected = (routeId) => this.handleRouteSelected(routeId);

    // 3. Initialize UI Subcomponents
    SimulationViewComponent.init();
    this.setupEventListeners();

    // 4. Initial evaluation or prompt user for input
    if (this.config.has_routes_backend_key) {
      await this.evaluateCurrentRoute(true);
    } else {
      this.showMissingCredentialsPrompt();
    }
  }

  updateConfigStatusUI() {
    const statusText = document.getElementById('statusText');
    const statusDot = document.getElementById('statusDot');
    const demoBanner = document.getElementById('demoBannerTag');
    if (demoBanner) demoBanner.style.display = 'none';

    if (!this.config.has_routes_backend_key || !this.config.has_gemini_backend_key) {
      statusText.textContent = "Online Mode (API Keys Required in .env)";
      statusDot.className = "status-dot";
      statusDot.style.background = "#eab308"; // Amber indicator
    } else {
      statusText.textContent = "Live Online Mode (Google & Gemini APIs)";
      statusDot.className = "status-dot live";
      statusDot.style.background = "#10b981"; // Emerald green
    }
  }

  showMissingCredentialsPrompt() {
    const container = document.getElementById('candidateRoutesContainer');
    if (container) {
      container.innerHTML = `
        <div class="empty-state" style="padding: 24px; text-align: left;">
          <h3 style="color: #f59e0b; margin-bottom: 8px;">🔑 API Credentials Required (.env)</h3>
          <p style="color: #cbd5e1; font-size: 0.9rem; line-height: 1.5; margin-bottom: 12px;">
            FlowSplit runs strictly in <strong>online mode</strong> without offline demo fallback or synthetic data.
          </p>
          <p style="color: #94a3b8; font-size: 0.85rem; line-height: 1.5;">
            To perform live routing and AI road inspection, configure your credentials in the root <code>.env</code> file:
          </p>
          <ul style="color: #94a3b8; font-size: 0.82rem; margin: 8px 0 16px 20px; line-height: 1.6;">
            <li><code>GOOGLE_ROUTES_API_KEY</code></li>
            <li><code>GOOGLE_STREET_VIEW_API_KEY</code></li>
            <li><code>GEMINI_API_KEY</code></li>
            <li><code>GOOGLE_MAPS_BROWSER_KEY</code> (optional for Google Maps JS)</li>
          </ul>
          <p style="color: #cbd5e1; font-size: 0.85rem;">
            Once supplied, enter origin and destination coordinates above and click <strong>Evaluate Routes</strong>.
          </p>
        </div>
      `;
    }
  }

  setupEventListeners() {
    // Search Form Submit
    const searchForm = document.getElementById('routeSearchForm');
    if (searchForm) {
      searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await this.evaluateCurrentRoute(false);
      });
    }

    // Geolocation "Use my location" button
    const btnUseLoc = document.getElementById('btnUseLocation');
    if (btnUseLoc) {
      btnUseLoc.addEventListener('click', async () => {
        await this.handleUseGeolocation();
      });
    }

    // Quick coordinates presets
    document.querySelectorAll('.preset-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');

        const originVal = e.currentTarget.dataset.origin;
        const destVal = e.currentTarget.dataset.dest;
        document.getElementById('originInput').value = originVal;
        document.getElementById('destinationInput').value = destVal;

        await this.evaluateCurrentRoute(false);
      });
    });

    // Confirm Route Button
    const btnConfirm = document.getElementById('btnConfirmRoute');
    if (btnConfirm) {
      btnConfirm.addEventListener('click', () => {
        const textSpan = document.getElementById('btnConfirmRouteText');
        textSpan.textContent = "✓ Route Active & Monitored";
        btnConfirm.classList.remove('btn-success');
        btnConfirm.classList.add('btn-primary');
        setTimeout(() => {
          textSpan.textContent = "Use This Recommended Route";
          btnConfirm.classList.remove('btn-primary');
          btnConfirm.classList.add('btn-success');
        }, 4000);
      });
    }

    // Map control buttons
    document.getElementById('btnZoomIn')?.addEventListener('click', () => this.mapController.zoomIn());
    document.getElementById('btnZoomOut')?.addEventListener('click', () => this.mapController.zoomOut());
    document.getElementById('btnResetView')?.addEventListener('click', () => this.mapController.resetView());
  }

  async handleUseGeolocation() {
    const feedback = document.getElementById('geolocationFeedback');
    feedback.textContent = "Requesting device coordinates...";

    try {
      const pos = await GeolocationService.getCurrentPosition();
      const coordStr = `${pos.lat.toFixed(6)}, ${pos.lng.toFixed(6)}`;
      document.getElementById('originInput').value = coordStr;
      feedback.textContent = `Location acquired (±${Math.round(pos.accuracy)}m)`;
      this.mapController.setUserLocation(pos.lat, pos.lng);
    } catch (err) {
      console.warn("Geolocation failed:", err);
      feedback.textContent = err.message;
    }
  }

  parseCoordinate(inputStr, defaultCoord) {
    if (!inputStr) return defaultCoord;
    const parts = inputStr.split(',').map(s => parseFloat(s.trim()));
    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
      return { lat: parts[0], lng: parts[1] };
    }
    return defaultCoord;
  }

  async evaluateCurrentRoute(isInitial = false) {
    const originStr = document.getElementById('originInput').value;
    const destStr = document.getElementById('destinationInput').value;
    const vehicleType = document.getElementById('vehicleTypeSelect').value || 'passenger_car';

    const origin = this.parseCoordinate(originStr, { lat: 37.7749, lng: -122.4494 });
    const destination = this.parseCoordinate(destStr, { lat: 37.7915, lng: -122.3999 });

    this.mapController.origin = origin;
    this.mapController.destination = destination;

    // Show loading state
    const spinner = document.getElementById('routeSearchSpinner');
    const btnText = document.getElementById('routeSearchBtnText');
    if (spinner) spinner.style.display = 'inline-block';
    if (btnText) btnText.textContent = "Connecting to Google & Gemini APIs...";

    try {
      // 1. Fetch Live Candidate Routes via Google Routes API
      const candidatesRes = await ApiClient.getCandidateRoutes(
        origin,
        destination,
        vehicleType
      );
      this.candidates = candidatesRes.candidates || [];

      // Render candidates on map & UI immediately
      this.selectedRouteId = this.candidates[0]?.id || null;
      this.mapController.setRoutes(this.candidates, this.selectedRouteId);
      RouteComparisonComponent.renderCandidateList(
        this.candidates,
        this.selectedRouteId,
        (id) => this.handleRouteSelected(id)
      );

      // Update provenance notice
      const provNotice = document.getElementById('provenanceText');
      if (provNotice) {
        provNotice.textContent = "Live Google Routes acquired. Running multimodal Gemini Vision inspection on physical road segments...";
      }

      if (btnText) btnText.textContent = "Inspecting Road Imagery with Gemini AI...";

      // 2. Visual inspection & suitability scoring via Street View + Gemini Vision
      const analysisRes = await ApiClient.analyzeRoutes(
        this.candidates,
        vehicleType
      );
      this.candidates = analysisRes.analyzed_candidates;

      if (provNotice) {
        provNotice.textContent = `Live inspection active (${analysisRes.analysis_provenance}). ${analysisRes.total_segments_analyzed} road segments evaluated.`;
      }

      // 3. FlowSplit Capacity-Aware Route Selection
      this.currentDecision = await ApiClient.selectBestRoute(
        this.candidates,
        null,
        vehicleType
      );

      this.selectedRouteId = this.currentDecision.selected_route_id;

      // 4. Update UI Components with complete AI findings
      RouteComparisonComponent.renderCandidateList(
        this.candidates,
        this.selectedRouteId,
        (id) => this.handleRouteSelected(id)
      );

      RouteComparisonComponent.updateSelectedDecisionCard(this.currentDecision);

      const selectedRoute = this.candidates.find(r => r.id === this.selectedRouteId);
      if (selectedRoute) {
        RoadDetailsComponent.renderSegmentInspection(selectedRoute);
      }

      // 5. Update Map with analyzed segments and hazard badges
      this.mapController.setRoutes(this.candidates, this.selectedRouteId);

    } catch (err) {
      console.error("Evaluation failed:", err);
      const container = document.getElementById('candidateRoutesContainer');
      if (container && (!this.candidates || this.candidates.length === 0)) {
        container.innerHTML = `
          <div class="empty-state" style="padding: 16px;">
            <p style="color: #f87171; font-weight: 600;">Routing Evaluation Error</p>
            <p style="color: #cbd5e1; font-size: 0.85rem; margin-top: 6px;">${err.message}</p>
          </div>
        `;
      } else if (!isInitial) {
        alert(`Online routing request error: ${err.message}`);
      }
    } finally {
      if (spinner) spinner.style.display = 'none';
      if (btnText) btnText.textContent = "Evaluate Routes";
    }
  }

  handleRouteSelected(routeId) {
    this.selectedRouteId = routeId;
    this.mapController.setSelectedRoute(routeId);

    // Re-render candidate list with active selection
    RouteComparisonComponent.renderCandidateList(
      this.candidates,
      this.selectedRouteId,
      (id) => this.handleRouteSelected(id)
    );

    // Update selected route card and deep-dive
    const route = this.candidates.find(r => r.id === routeId);
    if (route && this.currentDecision) {
      const decision = {
        ...this.currentDecision,
        selected_route_id: routeId,
        selected_route: route,
      };
      RouteComparisonComponent.updateSelectedDecisionCard(decision);
      RoadDetailsComponent.renderSegmentInspection(route);
    }
  }
}

// Start application on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new FlowSplitApp();
  app.init();
});
