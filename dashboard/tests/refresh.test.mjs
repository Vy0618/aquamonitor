import test from 'node:test';
import assert from 'node:assert/strict';
import { initializeFilters, refreshFilters, getFilterValues } from '../js/filters.js';
import { fetchStations } from '../js/api.js';

test('atualização inclui e remove opções, preservando seleções válidas e dependências', () => {
    const elements = Object.fromEntries(['stateFilter', 'cityFilter', 'districtFilter'].map(id => [id, {
        value: '', options: [], writes: 0,
        set innerHTML(value) { this.options = []; this.value = ''; this.writes++; },
        appendChild(option) { this.options.push(option); }
    }]));
    globalThis.document = { getElementById: id => elements[id], createElement: () => ({}) };
    const station = (state, city, district) => ({ administrative: { state, city, district } });
    const stations = [station('SP', 'Santos', 'Centro'), station('RJ', 'Rio', 'Centro')];
    initializeFilters(stations);
    elements.stateFilter.value = 'SP';
    elements.cityFilter.value = 'Santos';
    elements.districtFilter.value = 'Centro';
    refreshFilters(stations);
    assert.deepEqual(getFilterValues(), { state: 'SP', city: 'Santos', district: 'Centro' });
    const writes = elements.cityFilter.writes;
    refreshFilters(stations);
    assert.equal(elements.cityFilter.writes, writes, 'não reconstrói opções inalteradas');
    refreshFilters([...stations, station('SP', 'São Paulo', 'Sé')]);
    assert.deepEqual(elements.cityFilter.options.map(o => o.value), ['', 'Santos', 'São Paulo']);
    assert.equal(elements.cityFilter.value, 'Santos');
    refreshFilters([station('SP', 'São Paulo', 'Sé')]);
    assert.deepEqual(getFilterValues(), { state: 'SP', city: '', district: '' });
    refreshFilters([]);
    assert.deepEqual(getFilterValues(), { state: '', city: '', district: '' });
    delete globalThis.document;
});

test('API usa dados novos, propaga falhas e permite recuperar na consulta seguinte', async () => {
    const originalFetch = globalThis.fetch;
    try {
        globalThis.fetch = async (url, options) => {
            assert.equal(options.cache, 'no-store');
            assert.ok(options.signal instanceof AbortSignal);
            return { ok: true, json: async () => [{ station_id: 1 }] };
        };
        assert.equal((await fetchStations())[0].station_id, 1);
        globalThis.fetch = async () => ({ ok: false, status: 503 });
        await assert.rejects(fetchStations(), /503/);
        globalThis.fetch = async () => ({ ok: true, json: async () => ({}) });
        await assert.rejects(fetchStations(), /inválida/);
        globalThis.fetch = async () => ({ ok: true, json: async () => [] });
        assert.deepEqual(await fetchStations(), []);
    } finally {
        globalThis.fetch = originalFetch;
    }
});
