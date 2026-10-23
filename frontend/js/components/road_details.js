/**
 * Road Details Component
 * Inspects and renders detailed segment-by-segment visual inference from Gemini.
 */

const RoadDetailsComponent = {
  renderSegmentInspection(route) {
    const card = document.getElementById('roadInspectionCard');
    const container = document.getElementById('segmentsAccordionContainer');

    if (!route || !route.segments || route.segments.length === 0) {
      card.style.display = 'none';
      return;
    }

    card.style.display = 'block';
    container.innerHTML = '';

    route.segments.forEach((seg, idx) => {
      const vision = seg.vision_analysis || {};
      const suitability = seg.suitability || {};
      const score = Math.round(suitability.suitability_score || 50);

      const item = document.createElement('div');
      item.className = 'segment-item';

      const widthStr = vision.usable_road_width_meters ? `${vision.usable_road_width_meters.toFixed(1)}m` : 'Unknown / Ambiguous';
      const lanesStr = vision.visible_lane_count ? `${vision.visible_lane_count} lane(s)` : 'Shared single corridor';
      const parkingStr = vision.parking_obstruction ? vision.parking_obstruction.toUpperCase() : 'NONE';
      const pedContext = (vision.pedestrian_cyclist_activity || 'low').replace(/_/g, ' ');
      const obstacles = (vision.visible_obstacles && vision.visible_obstacles.length) ? vision.visible_obstacles.join(', ') : 'None detected';
      const evidence = (vision.evidence_notes && vision.evidence_notes.length) ? vision.evidence_notes.join(' ') : 'Visual inspection inferred from geometry.';

      item.innerHTML = `
        <div class="segment-header" data-toggle="collapse">
          <span class="segment-name">${seg.name}</span>
          <span class="segment-meta">Suitability: <strong>${score}/100</strong> (${Math.round(seg.length_meters)}m)</span>
        </div>
        <div class="segment-content" style="${idx === 0 ? 'display: flex;' : 'display: none;'}">
          <div class="vision-row">
            <span>Usable Width:</span>
            <strong>${widthStr}</strong>
          </div>
          <div class="vision-row">
            <span>Visible Lanes:</span>
            <strong>${lanesStr}</strong>
          </div>
          <div class="vision-row">
            <span>Curbside Parking Friction:</span>
            <strong>${parkingStr}</strong>
          </div>
          <div class="vision-row">
            <span>Pedestrian Context:</span>
            <strong>${pedContext}</strong>
          </div>
          <div class="vision-row">
            <span>Hazards / Obstacles:</span>
            <strong>${obstacles}</strong>
          </div>
          <div class="evidence-notes">
            " ${evidence} "
          </div>
        </div>
      `;

      // Header click toggles accordion content
      const header = item.querySelector('.segment-header');
      const content = item.querySelector('.segment-content');
      header.addEventListener('click', () => {
        const isClosed = content.style.display === 'none';
        content.style.display = isClosed ? 'flex' : 'none';
      });

      container.appendChild(item);
    });
  },
};
