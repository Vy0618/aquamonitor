import test from 'node:test';
import assert from 'node:assert/strict';
import { bottleDirections, formatBottleDirections } from '../js/directions.js';

test('sentidos das garrafas não incluem outras classes', () => {
    const summary = { total: 20, by_type: { bottle: 5, can: 15 },
        by_direction: { positive: 18, negative: 2, unknown: 0 },
        by_type_direction: { bottle: { positive: 3, negative: 2, unknown: 0 } } };
    assert.deepEqual(bottleDirections(summary), { positive: 3, negative: 2, unknown: 0 });
    assert.equal(formatBottleDirections(summary), '↓ Positivo: 3 · ↑ Negativo: 2 · Não informado: 0');
});

test('API antiga e estado vazio não inventam um sentido', () => {
    assert.deepEqual(bottleDirections({ by_type: { bottle: 7, can: 8 } }),
        { positive: 0, negative: 0, unknown: 7 });
    assert.deepEqual(bottleDirections(null), { positive: 0, negative: 0, unknown: 0 });
});
