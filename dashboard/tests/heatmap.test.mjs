import test from 'node:test';
import assert from 'node:assert/strict';
import { buildHeatData, calculateIntensity, createHeatmap, updateMap } from '../js/heatmap.js';
import { markerDiameter } from '../js/markers.js';

const station = (id, count) => ({ station_id: id, detections: count,
    location: { coordinates: [-46, -23] } });

test('intensidade linear, referência fixa e exclusão de contagens inválidas ou zero', () => {
    assert.equal(calculateIntensity(100) / calculateIntensity(10), 10);
    assert.equal(calculateIntensity(300), 1);
    assert.equal(calculateIntensity(600), 2);
    const stations = [station(1, 10), station(2, 100), station(3, 0), station(4, -1), station(5, NaN)];
    const all = buildHeatData(stations);
    assert.equal(all.length, 2);
    assert.deepEqual(buildHeatData([stations[0]])[0], all[0]);
    assert.deepEqual(buildHeatData([]), []);
    assert.deepEqual(buildHeatData([{ ...station(6, 100), detection_summary: { total: 0 } }]), []);
});

test('área proporcional dos círculos, limites e anéis compactos', () => {
    assert.ok(Math.abs((markerDiameter(100) / markerDiameter(25)) ** 2 - 4) < 1e-10);
    assert.equal(markerDiameter(0), 8);
    assert.equal(markerDiameter(600), markerDiameter(300));
    assert.equal(markerDiameter(300, 'both'), 12);
});

test('modos alternam camadas sem perder calor, filtros ou marcadores zerados', () => {
    const visible = new Set();
    const map = { hasLayer: layer => visible.has(layer), removeLayer: layer => visible.delete(layer) };
    let heatOptions;
    globalThis.L = {
        heatLayer(data, options) {
            heatOptions = options;
            return { data, addTo() { visible.add(this); return this; },
                setLatLngs(value) { this.data = value; }, setOptions() {} };
        },
        divIcon: options => ({ options }),
        marker(coords, options) {
            return { options, bindTooltip() {}, bindPopup() {}, on() {}, isPopupOpen: () => false, openPopup() {} };
        }
    };
    const stations = [station(1, 100), station(2, 0)];
    const heat = createHeatmap(map, stations);
    assert.equal(heatOptions.maxZoom, 0);
    assert.equal(heatOptions.minOpacity, 0.01);
    const markerLayer = { layers: [], getLayers() { return this.layers; },
        clearLayers() { this.layers = []; }, addLayer(layer) { this.layers.push(layer); },
        addTo() { visible.add(this); } };
    const args = { map, heat, markerLayer, stations, filterStations: items => items };
    updateMap(args);
    assert.ok(visible.has(heat));
    assert.ok(!visible.has(markerLayer));
    updateMap({ ...args, mode: 'stations' });
    assert.ok(!visible.has(heat));
    assert.ok(visible.has(markerLayer));
    assert.equal(markerLayer.layers.length, 2);
    updateMap({ ...args, mode: 'both', filterStations: items => items.slice(1) });
    assert.ok(visible.has(heat));
    assert.ok(visible.has(markerLayer));
    assert.equal(markerLayer.layers.length, 1);
    assert.deepEqual(heat.data, []);
    updateMap(args);
    assert.equal(heat.data.length, 1);
    assert.ok(!visible.has(markerLayer));
    delete globalThis.L;
});
