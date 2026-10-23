/**
 * Browser Geolocation Service
 * Safely requests device coordinates via navigator.geolocation with user permission.
 */

const GeolocationService = {
  isSupported() {
    return 'geolocation' in navigator;
  },

  isSecureContext() {
    return window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  },

  getCurrentPosition() {
    return new Promise((resolve, reject) => {
      if (!this.isSupported()) {
        reject(new Error("Browser Geolocation is not supported on this device."));
        return;
      }

      if (!this.isSecureContext()) {
        reject(new Error("Geolocation requires a secure HTTPS connection or localhost."));
        return;
      }

      const options = {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 30000,
      };

      navigator.geolocation.getCurrentPosition(
        (position) => {
          const lat = position.coords.latitude;
          const lng = position.coords.longitude;

          // Validate coordinate sanity
          if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
            reject(new Error("Received invalid latitude/longitude from geolocation hardware."));
            return;
          }

          resolve({
            lat: Number(lat.toFixed(6)),
            lng: Number(lng.toFixed(6)),
            accuracy: position.coords.accuracy,
          });
        },
        (error) => {
          switch (error.code) {
            case error.PERMISSION_DENIED:
              reject(new Error("Location permission denied. Please enter origin coordinates manually."));
              break;
            case error.POSITION_UNAVAILABLE:
              reject(new Error("Location information is currently unavailable."));
              break;
            case error.TIMEOUT:
              reject(new Error("Location request timed out."));
              break;
            default:
              reject(new Error(`Location error: ${error.message}`));
              break;
          }
        },
        options
      );
    });
  },
};
