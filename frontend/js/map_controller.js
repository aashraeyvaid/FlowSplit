/**
 * FlowSplit Map Controller
 * Seamlessly toggles between Google Maps JavaScript API and a built-in interactive
 * Canvas/Vector map engine for complete offline and zero-config operation.
 */

class MapController {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.mode = 'canvas'; // 'google' or 'canvas'
    this.googleMap = null;
    this.googlePolylines = [];
    this.googleMarkers = [];
    
    // Canvas Engine State
    this.canvas = null;
    this.ctx = null;
    this.routes = [];
    this.selectedRouteId = null;
    this.userLocation = null;
    this.origin = { lat: 37.7749, lng: -122.4494 };
    this.destination = { lat: 37.7915, lng: -122.3999 };
    
    // Viewport transform
    this.zoom = 13.5;
    this.center = { lat: 37.7832, lng: -122.4246 };
    this.isDragging = false;
    this.dragStart = { x: 0, y: 0 };
    
    // Callbacks
    this.onRouteSelected = null;
  }

  async init(browserApiKey = null, mapsJsUrl = "https://maps.googleapis.com/maps/api/js") {
    // Graceful fallback if Google Maps JS fails authentication on localhost / domain
    window.gm_authFailure = () => {
      console.warn("Google Maps JS API authentication failed. Switching to interactive Canvas Vector engine.");
      const hud = document.getElementById('hudEngineLabel');
      if (hud) hud.textContent = "Interactive Vector / Canvas (Active)";
      this.mode = 'canvas';
      this.initCanvasMap();
      if (this.routes && this.routes.length) {
        this.fitBoundsToRoutes();
        this.renderCanvas();
      }
    };

    if (browserApiKey) {
      try {
        await this.loadGoogleMapsScript(browserApiKey, mapsJsUrl);
        this.initGoogleMap();
        this.mode = 'google';
        const hud = document.getElementById('hudEngineLabel');
        if (hud) hud.textContent = "Google Maps JS API (Live)";
        return;
      } catch (err) {
        console.warn("Failed to load Google Maps JS API, falling back to Canvas engine:", err);
      }
    }

    this.initCanvasMap();
    this.mode = 'canvas';
    const hud = document.getElementById('hudEngineLabel');
    if (hud) hud.textContent = "Interactive Vector / Canvas";
  }

  loadGoogleMapsScript(apiKey, mapsJsUrl = "https://maps.googleapis.com/maps/api/js") {
    return new Promise((resolve, reject) => {
      if (window.google && window.google.maps) {
        resolve();
        return;
      }
      const script = document.createElement('script');
      const cleanUrl = mapsJsUrl.includes('?') ? mapsJsUrl : `${mapsJsUrl}?key=${apiKey}&libraries=places`;
      script.src = cleanUrl;
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Google Maps script load error"));
      document.head.appendChild(script);
    });
  }

  initGoogleMap() {
    this.container.innerHTML = '';
    const lightTransitStyle = [
      { elementType: "geometry", stylers: [{ color: "#f8fafc" }] },
      { elementType: "labels.text.stroke", stylers: [{ color: "#ffffff" }] },
      { elementType: "labels.text.fill", stylers: [{ color: "#475569" }] },
      { featureType: "road", elementType: "geometry", stylers: [{ color: "#ffffff" }] },
      { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#e2e8f0" }] },
      { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#ffedd5" }] },
      { featureType: "road.highway", elementType: "geometry.stroke", stylers: [{ color: "#fed7aa" }] },
      { featureType: "water", elementType: "geometry", stylers: [{ color: "#e0f2fe" }] },
      { featureType: "water", elementType: "labels.text.fill", stylers: [{ color: "#0284c7" }] },
      { featureType: "transit", elementType: "geometry", stylers: [{ color: "#f1f5f9" }] },
      { featureType: "poi", elementType: "labels", stylers: [{ visibility: "off" }] },
    ];

    this.googleMap = new google.maps.Map(this.container, {
      center: this.center,
      zoom: 13,
      styles: lightTransitStyle,
      disableDefaultUI: false,
      zoomControl: true,
      mapTypeControl: false,
    });
  }

  initCanvasMap() {
    this.container.innerHTML = '';
    this.canvas = document.createElement('canvas');
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';
    this.canvas.style.display = 'block';
    this.canvas.style.cursor = 'grab';
    this.container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');

    this.resizeCanvas();
    window.addEventListener('resize', () => {
      this.resizeCanvas();
      this.renderCanvas();
    });

    // Mouse Interaction
    this.canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.dragStart = { x: e.clientX, y: e.clientY };
      this.canvas.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isDragging) return;
      const dx = e.clientX - this.dragStart.x;
      const dy = e.clientY - this.dragStart.y;
      this.dragStart = { x: e.clientX, y: e.clientY };

      const scale = Math.pow(2, this.zoom) * 256 / 360;
      this.center.lng -= dx / scale;
      this.center.lat += (dy / scale) * Math.cos(this.center.lat * Math.PI / 180);
      this.renderCanvas();
    });

    window.addEventListener('mouseup', () => {
      if (this.isDragging) {
        this.isDragging = false;
        if (this.canvas) this.canvas.style.cursor = 'grab';
      }
    });

    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 0.2 : -0.2;
      this.zoom = Math.max(10, Math.min(18, this.zoom + zoomFactor));
      this.renderCanvas();
    });

    // Route click detection
    this.canvas.addEventListener('click', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      this.handleCanvasClick(mouseX, mouseY);
    });

    this.renderCanvas();
  }

  resizeCanvas() {
    if (!this.canvas || !this.ctx) return;
    const rect = this.container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.scale(dpr, dpr);
  }

  latLngToPixel(lat, lng) {
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    const scale = Math.pow(2, this.zoom) * 256 / 360;
    const cosLat = Math.cos(this.center.lat * Math.PI / 180);

    const x = width / 2 + (lng - this.center.lng) * scale;
    const y = height / 2 - (lat - this.center.lat) * scale / cosLat;
    return { x, y };
  }

  pixelToLatLng(x, y) {
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    const scale = Math.pow(2, this.zoom) * 256 / 360;
    const cosLat = Math.cos(this.center.lat * Math.PI / 180);

    const lng = this.center.lng + (x - width / 2) / scale;
    const lat = this.center.lat - (y - height / 2) * cosLat / scale;
    return { lat, lng };
  }

  setRoutes(routes, selectedRouteId = null) {
    this.routes = routes || [];
    this.selectedRouteId = selectedRouteId || (routes.length ? routes[0].id : null);

    this.updateMapLegendUI();

    if (this.mode === 'google' && this.googleMap && window.google && window.google.maps) {
      try {
        this.renderGoogleRoutes();
        return;
      } catch (err) {
        console.warn("renderGoogleRoutes error, rendering canvas fallback:", err);
      }
    }

    if (!this.canvas) {
      this.initCanvasMap();
    }
    this.fitBoundsToRoutes();
    this.renderCanvas();
  }

  updateMapLegendUI() {
    const legendEl = document.getElementById('mapLegend');
    if (!legendEl) return;

    if (!this.routes || this.routes.length === 0) {
      legendEl.innerHTML = `
        <div class="legend-header">Candidate Paths</div>
        <div class="legend-item"><span class="legend-text" style="color: #94a3b8;">Awaiting live route evaluation...</span></div>
      `;
      return;
    }

    let itemsHtml = '<div class="legend-header">Candidate Paths (Online)</div>';
    this.routes.forEach(r => {
      const isSelected = r.id === this.selectedRouteId;
      itemsHtml += `
        <div class="legend-item ${isSelected ? 'active-legend' : ''}" style="cursor: pointer;" data-route-id="${r.id}">
          <span class="legend-color-bar" style="background: ${r.route_color || '#3b82f6'};"></span>
          <span class="legend-text" style="${isSelected ? 'font-weight: 700; color: #fff;' : ''}">${r.name}</span>
        </div>
      `;
    });
    legendEl.innerHTML = itemsHtml;

    // Allow clicking legend to switch selected route
    legendEl.querySelectorAll('.legend-item').forEach(item => {
      item.addEventListener('click', () => {
        const routeId = item.getAttribute('data-route-id');
        if (routeId && this.onRouteSelected) {
          this.onRouteSelected(routeId);
        }
      });
    });
  }

  setSelectedRoute(routeId) {
    this.selectedRouteId = routeId;
    if (this.mode === 'google') {
      this.highlightGoogleRoute(routeId);
    } else {
      this.renderCanvas();
    }
  }

  clearGoogleOverlays() {
    if (this.googlePolylines) {
      this.googlePolylines.forEach(item => {
        if (item.polyline) item.polyline.setMap(null);
      });
      this.googlePolylines = [];
    }
    if (this.googleMarkers) {
      this.googleMarkers.forEach(marker => {
        if (marker) marker.setMap(null);
      });
      this.googleMarkers = [];
    }
  }

  renderGoogleRoutes() {
    if (!this.googleMap || !window.google || !google.maps) return;
    this.clearGoogleOverlays();

    if (!this.routes || this.routes.length === 0) return;

    const bounds = new google.maps.LatLngBounds();

    this.routes.forEach(route => {
      const isSelected = route.id === this.selectedRouteId;
      const coords = (route.coordinates || []).map(c => ({ lat: c.lat, lng: c.lng }));
      if (coords.length === 0) return;

      coords.forEach(pt => bounds.extend(pt));

      const polyline = new google.maps.Polyline({
        path: coords,
        geodesic: true,
        strokeColor: isSelected ? '#ea580c' : (route.route_color || '#94a3b8'),
        strokeOpacity: isSelected ? 1.0 : 0.5,
        strokeWeight: isSelected ? 6 : 4,
        zIndex: isSelected ? 100 : 10,
        map: this.googleMap,
      });

      polyline.addListener('click', () => {
        this.setSelectedRoute(route.id);
        if (this.onRouteSelected) {
          this.onRouteSelected(route.id);
        }
      });

      this.googlePolylines.push({
        routeId: route.id,
        polyline: polyline,
        color: route.route_color || '#94a3b8',
      });
    });

    // Origin marker (Pin A)
    if (this.origin) {
      const origMarker = new google.maps.Marker({
        position: this.origin,
        map: this.googleMap,
        title: "Origin",
        label: { text: "A", color: "#ffffff", fontWeight: "bold" },
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 11,
          fillColor: "#ea580c",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 3,
        },
      });
      this.googleMarkers.push(origMarker);
      bounds.extend(this.origin);
    }

    // Destination marker (Pin B)
    if (this.destination) {
      const destMarker = new google.maps.Marker({
        position: this.destination,
        map: this.googleMap,
        title: "Destination",
        label: { text: "B", color: "#ffffff", fontWeight: "bold" },
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 11,
          fillColor: "#0f172a",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 3,
        },
      });
      this.googleMarkers.push(destMarker);
      bounds.extend(this.destination);
    }

    // User location marker if present
    if (this.userLocation) {
      const userMarker = new google.maps.Marker({
        position: this.userLocation,
        map: this.googleMap,
        title: "Your Location",
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: "#ea580c",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 2,
        },
      });
      this.googleMarkers.push(userMarker);
    }

    if (!bounds.isEmpty()) {
      this.googleMap.fitBounds(bounds, { top: 50, right: 50, bottom: 50, left: 50 });
    }
  }

  highlightGoogleRoute(routeId) {
    if (!this.googlePolylines) return;
    this.googlePolylines.forEach(item => {
      const isSelected = item.routeId === routeId;
      item.polyline.setOptions({
        strokeColor: isSelected ? '#ea580c' : (item.color || '#94a3b8'),
        strokeOpacity: isSelected ? 1.0 : 0.5,
        strokeWeight: isSelected ? 6 : 4,
        zIndex: isSelected ? 100 : 10,
      });
    });
  }

  setUserLocation(lat, lng) {
    this.userLocation = { lat, lng };
    this.origin = { lat, lng };
    this.center = { lat, lng };
    if (this.mode === 'google' && this.googleMap) {
      new google.maps.Marker({
        position: { lat, lng },
        map: this.googleMap,
        title: "Your Location",
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: "#38bdf8",
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 2,
        },
      });
      this.googleMap.setCenter({ lat, lng });
    } else {
      this.renderCanvas();
    }
  }

  fitBoundsToRoutes() {
    if (!this.routes.length) return;
    let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
    this.routes.forEach(r => {
      (r.coordinates || []).forEach(pt => {
        if (pt.lat < minLat) minLat = pt.lat;
        if (pt.lat > maxLat) maxLat = pt.lat;
        if (pt.lng < minLng) minLng = pt.lng;
        if (pt.lng > maxLng) maxLng = pt.lng;
      });
    });

    if (minLat <= maxLat) {
      this.center = {
        lat: (minLat + maxLat) / 2,
        lng: (minLng + maxLng) / 2,
      };
    }
  }

  renderCanvas() {
    if (!this.ctx || !this.canvas) return;
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;

    // 1. Clean modern light geospatial canvas background
    this.ctx.fillStyle = '#f8fafc';
    this.ctx.fillRect(0, 0, width, height);

    // 2. Subtle geometric grid lines
    this.ctx.strokeStyle = '#e2e8f0';
    this.ctx.lineWidth = 1;
    const gridSize = 60;
    for (let x = 0; x < width; x += gridSize) {
      this.ctx.beginPath();
      this.ctx.moveTo(x, 0);
      this.ctx.lineTo(x, height);
      this.ctx.stroke();
    }
    for (let y = 0; y < height; y += gridSize) {
      this.ctx.beginPath();
      this.ctx.moveTo(0, y);
      this.ctx.lineTo(width, y);
      this.ctx.stroke();
    }

    // 3. Draw Candidate Routes
    this.routes.forEach(route => {
      const isSelected = route.id === this.selectedRouteId;
      const coords = route.coordinates || [];
      if (coords.length < 2) return;

      this.ctx.beginPath();
      coords.forEach((pt, i) => {
        const pix = this.latLngToPixel(pt.lat, pt.lng);
        if (i === 0) this.ctx.moveTo(pix.x, pix.y);
        else this.ctx.lineTo(pix.x, pix.y);
      });

      if (isSelected) {
        // Soft orange halo layer
        this.ctx.strokeStyle = '#fed7aa';
        this.ctx.lineWidth = 10;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        this.ctx.stroke();

        // Primary transit orange line
        this.ctx.strokeStyle = '#ea580c';
        this.ctx.lineWidth = 5;
        this.ctx.stroke();
      } else {
        // Unselected alternative route line
        this.ctx.strokeStyle = '#94a3b8';
        this.ctx.lineWidth = 4;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        this.ctx.globalAlpha = 0.65;
        this.ctx.stroke();
        this.ctx.globalAlpha = 1.0;
      }
    });

    // 4. Draw choke point / hazard indicators on segments
    this.routes.forEach(route => {
      (route.segments || []).forEach(seg => {
        if (seg.suitability && seg.suitability.suitability_score < 40) {
          const pt = this.latLngToPixel(seg.start_coord.lat, seg.start_coord.lng);
          // Warning indicator circle
          this.ctx.fillStyle = '#dc2626';
          this.ctx.beginPath();
          this.ctx.arc(pt.x, pt.y, 6, 0, Math.PI * 2);
          this.ctx.fill();
          this.ctx.strokeStyle = '#ffffff';
          this.ctx.lineWidth = 2;
          this.ctx.stroke();
        }
      });
    });

    // 5. Draw Origin and Destination Pins
    if (this.origin) {
      const origPix = this.latLngToPixel(this.origin.lat, this.origin.lng);
      this.drawPin(origPix.x, origPix.y, '#ea580c', 'START');
    }
    if (this.destination) {
      const destPix = this.latLngToPixel(this.destination.lat, this.destination.lng);
      this.drawPin(destPix.x, destPix.y, '#0f172a', 'END');
    }

    // 6. Draw User Location if available
    if (this.userLocation) {
      const userPix = this.latLngToPixel(this.userLocation.lat, this.userLocation.lng);
      this.ctx.fillStyle = 'rgba(234, 88, 12, 0.2)';
      this.ctx.beginPath();
      this.ctx.arc(userPix.x, userPix.y, 14, 0, Math.PI * 2);
      this.ctx.fill();

      this.ctx.fillStyle = '#ea580c';
      this.ctx.beginPath();
      this.ctx.arc(userPix.x, userPix.y, 6, 0, Math.PI * 2);
      this.ctx.fill();
    }
  }

  drawPin(x, y, color, label) {
    this.ctx.fillStyle = color;
    this.ctx.beginPath();
    this.ctx.arc(x, y, 9, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.strokeStyle = '#ffffff';
    this.ctx.lineWidth = 2.5;
    this.ctx.stroke();

    this.ctx.fillStyle = '#ffffff';
    this.ctx.font = 'bold 9px Outfit, sans-serif';
    this.ctx.textAlign = 'center';
    this.ctx.fillText(label, x, y - 13);
  }

  handleCanvasClick(x, y) {
    // Check if clicked close to any route line
    for (const route of this.routes) {
      const coords = route.coordinates || [];
      for (let i = 0; i < coords.length - 1; i++) {
        const p1 = this.latLngToPixel(coords[i].lat, coords[i].lng);
        const p2 = this.latLngToPixel(coords[i + 1].lat, coords[i + 1].lng);

        const dist = this.distToSegment({ x, y }, p1, p2);
        if (dist < 15) {
          this.setSelectedRoute(route.id);
          if (this.onRouteSelected) {
            this.onRouteSelected(route.id);
          }
          return;
        }
      }
    }
  }

  distToSegment(p, v, w) {
    const l2 = (v.x - w.x) * (v.x - w.x) + (v.y - w.y) * (v.y - w.y);
    if (l2 === 0) return Math.hypot(p.x - v.x, p.y - v.y);
    let t = ((p.x - v.x) * (w.x - v.x) + (p.y - v.y) * (w.y - v.y)) / l2;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(p.x - (v.x + t * (w.x - v.x)), p.y - (v.y + t * (w.y - v.y)));
  }

  zoomIn() {
    this.zoom = Math.min(18, this.zoom + 0.5);
    if (this.mode === 'google' && this.googleMap) {
      this.googleMap.setZoom(this.googleMap.getZoom() + 1);
    } else {
      this.renderCanvas();
    }
  }

  zoomOut() {
    this.zoom = Math.max(10, this.zoom - 0.5);
    if (this.mode === 'google' && this.googleMap) {
      this.googleMap.setZoom(this.googleMap.getZoom() - 1);
    } else {
      this.renderCanvas();
    }
  }

  resetView() {
    this.zoom = 13.5;
    this.fitBoundsToRoutes();
    if (this.mode === 'google' && this.googleMap) {
      this.googleMap.setCenter(this.center);
      this.googleMap.setZoom(13);
    } else {
      this.renderCanvas();
    }
  }
}
