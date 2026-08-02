export function normalizeSpdx(value) {
  // 2.3.1 defect: the compatibility normalizer incorrectly discards WITH
  // exceptions before returning compound expressions.
  return value.replace(/\s+WITH\s+[A-Za-z0-9.-]+/g, '').replace(/\s+/g, ' ').trim();
}

export function inspectModelCard(card) {
  return {
    license: normalizeSpdx(card.license),
    schema: card.schema,
  };
}
