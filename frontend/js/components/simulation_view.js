/**
 * Simulation View Component
 * Controls the interactive Traffic Simulation Lab modal comparing Baseline vs FlowSplit.
 * Operates across online-retrieved candidate routes.
 */

const SimulationViewComponent = {
  modalEl: null,

  init() {
    this.modalEl = document.getElementById('simulationModal');
    const btnOpen = document.getElementById('btnOpenSimulation');
    const btnClose = document.getElementById('btnCloseSimulation');
    const btnRun = document.getElementById('btnRunSimSimulation');

    if (btnOpen) {
      btnOpen.addEventListener('click', () => {
        this.openModal();
      });
    }

    if (btnClose) {
      btnClose.addEventListener('click', () => {
        this.closeModal();
      });
    }

    if (btnRun) {
      btnRun.addEventListener('click', async () => {
        const input = document.getElementById('simDemandInput');
        const trips = parseInt(input.value, 10) || 900;
        await this.runSimulation(trips);
      });
    }

    // Close on backdrop click
    if (this.modalEl) {
      this.modalEl.addEventListener('click', (e) => {
        if (e.target === this.modalEl) this.closeModal();
      });
    }
  },

  openModal() {
    if (this.modalEl) {
      this.modalEl.style.display = 'flex';
      this.runSimulation(900);
    }
  },

  closeModal() {
    if (this.modalEl) {
      this.modalEl.style.display = 'none';
    }
  },

  async runSimulation(trips = 900) {
    try {
      const candidates = (window.flowsplitApp && window.flowsplitApp.candidates && window.flowsplitApp.candidates.length)
        ? window.flowsplitApp.candidates
        : null;
      const data = await ApiClient.runSimulation(trips, candidates);
      this.renderSimulationResults(data);
    } catch (err) {
      console.error("Failed to run traffic simulation:", err);
      alert(`Simulation failed: ${err.message}`);
    }
  },

  renderSimulationResults(data) {
    const base = data.baseline_result;
    const flow = data.flowsplit_result;

    // 1. Average transit time
    const baseTimeMin = (base.average_travel_time_seconds / 60).toFixed(1);
    const flowTimeMin = (flow.average_travel_time_seconds / 60).toFixed(1);
    document.getElementById('simBaselineAvgTime').textContent = `${baseTimeMin} min`;
    document.getElementById('simFlowSplitAvgTime').textContent = `${flowTimeMin} min`;
    document.getElementById('simTimeDeltaBadge').textContent = `−${data.travel_time_delta_percent.toFixed(0)}% Transit Time`;

    // 2. Queue Length
    document.getElementById('simBaselineQueue').textContent = `${Math.round(base.maximum_queue_vehicles)} vehicles`;
    document.getElementById('simFlowSplitQueue').textContent = `${Math.round(flow.maximum_queue_vehicles)} vehicles`;
    document.getElementById('simQueueDeltaBadge').textContent = `−${data.queue_reduction_percent.toFixed(0)}% Queue`;

    // 3. Overloaded segments
    document.getElementById('simBaselineOverloaded').textContent = `${base.overloaded_segments_count} segments`;
    document.getElementById('simFlowSplitOverloaded').textContent = `${flow.overloaded_segments_count} segments`;

    // 4. Volume Allocation Table
    const tbody = document.getElementById('simAllocationsTableBody');
    if (tbody) {
      tbody.innerHTML = '';
      (data.candidates || []).forEach(cand => {
        const baseAlloc = base.route_allocations[cand.id] || 0;
        const flowAlloc = flow.route_allocations[cand.id] || 0;
        const segCap = (cand.segments && cand.segments.length)
          ? Math.round(cand.segments[0].nominal_capacity_vph)
          : (cand.id.includes('shortcut') ? 250 : 1200);

        const isOverloaded = baseAlloc > segCap;

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${cand.name}</strong></td>
          <td>${segCap.toLocaleString()} veh/hr</td>
          <td><span class="badge ${cand.suitability_score >= 70 ? 'badge-success' : 'badge-danger'}">${Math.round(cand.suitability_score || 50)}/100</span></td>
          <td style="color: ${isOverloaded ? '#f87171' : 'inherit'}; font-weight: 700;">
            ${baseAlloc} trips (${Math.round((baseAlloc / data.total_hourly_demand_vehicles) * 100)}%)
          </td>
          <td style="color: #34d399; font-weight: 700;">
            ${flowAlloc} trips (${Math.round((flowAlloc / data.total_hourly_demand_vehicles) * 100)}%)
          </td>
          <td>
            <span class="badge ${isOverloaded ? 'badge-danger' : 'badge-success'}">
              ${isOverloaded ? 'GRIDLOCK IN BASELINE' : 'CAPACITY PROTECTED'}
            </span>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    // 5. Verdict text
    const verdictEl = document.getElementById('simVerdictText');
    if (verdictEl) {
      verdictEl.textContent = (
        `Simulation Results for ${data.total_hourly_demand_vehicles} Commuter Trips: ` +
        `Baseline GPS concentrated uncoordinated drivers onto single shortest corridors, creating ` +
        `${base.overloaded_segments_count} bottlenecked segments and an average transit time of ${baseTimeMin} minutes. ` +
        `FlowSplit's capacity-aware optimization protected corridor limits, lowering maximum queue length by ` +
        `${data.queue_reduction_percent.toFixed(0)}% and improving transit time to ${flowTimeMin} minutes.`
      );
    }
  },
};
