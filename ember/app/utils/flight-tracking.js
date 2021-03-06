/* globals $ */

import Ember from 'ember';
import ol from 'openlayers';

export default Ember.Object.extend({
  flight_display: null,
  flights: null,

  init() {
    window.fixCalcService.set('defaultTime', -1);
    window.fixCalcService.set('time', -1);
  },

  /**
   * Retrieves all new traces for the displayed flights
   */
  updateFlightsFromJSON() {
    let flight_display = this.get('flight_display');

    this.get('flights').forEach(flight => {
      let url = `/tracking/${flight.get('id')}/json`;

      $.ajax(url, {
        data: { last_update: flight.get('last_update') || null },
        success: data => {
          this.updateFlight(data);
          flight_display.update();
        },
      });
    });
  },

  /**
   * Updates a tracking flight.
   *
   * @param {Object} data The data returned by the JSON request.
   */
  updateFlight(data) {
    // find the flight to update
    let flight = this.get('flights').findBy('id', data.sfid);
    if (!flight)
      return;

    let time_decoded = ol.format.Polyline.decodeDeltas(data.barogram_t, 1, 1);
    let lonlat = ol.format.Polyline.decodeDeltas(data.points, 2);
    let height_decoded = ol.format.Polyline.decodeDeltas(data.barogram_h, 1, 1);
    let enl_decoded = ol.format.Polyline.decodeDeltas(data.enl, 1, 1);
    let elev = ol.format.Polyline.decodeDeltas(data.elevations, 1, 1);

    // we skip the first point in the list because we assume it's the "linking"
    // fix between the data we already have and the data to add.
    if (time_decoded.length < 2) return;

    let geoid = flight.get('geoid');

    let fixes = time_decoded.map(function(timestamp, i) {
      return {
        time: timestamp,
        longitude: lonlat[i * 2],
        latitude: lonlat[i * 2 + 1],
        altitude: height_decoded[i] + geoid,
        enl: enl_decoded[i],
      };
    });

    let elevations = time_decoded.map(function(timestamp, i) {
      let elevation = elev[i];

      return {
        time: timestamp,
        elevation: (elevation > -500) ? elevation : null,
      };
    });

    flight.get('fixes').pushObjects(fixes.slice(1));
    flight.get('elevations').pushObjects(elevations.slice(1));
  },
});
