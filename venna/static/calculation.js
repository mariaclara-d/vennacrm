const areaScale = 10_000n;
const wholeFormatter = new Intl.NumberFormat('pt-BR');
const currencyFormatter = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
});

export function parseAmount(input, type, optional = false) {
  const isArea = type === 'area';
  const decimals = isArea ? 4 : 2;
  const value = input.trim();

  if (!value) {
    const requiredMessage = isArea ? 'Informe a metragem.' : 'Informe o preço por m².';
    return { units: null, error: optional ? '' : requiredMessage };
  }

  const number = isArea ? value : value.replace(/^R\$\s*/, '');
  const usesGrouping = /^[1-9]\d{0,2}(?:\.\d{3})+(?:,\d+)?$/.test(number);
  const normalized = usesGrouping ? number.replaceAll('.', '') : number;
  const match = /^(\d+)(?:[,.](\d+))?$/.exec(normalized);

  if (!match) {
    return { units: null, error: 'Informe um número sem sinal. Ex.: 1.250,50.' };
  }

  const [, integer, fraction = ''] = match;
  if (fraction.length > decimals) {
    return { units: null, error: `Use até ${decimals} casas decimais.` };
  }

  const whole = BigInt(integer);
  if (whole > 999_999_999n) {
    return { units: null, error: 'Informe um valor com até 9 dígitos inteiros.' };
  }

  const scale = isArea ? areaScale : 100n;
  const units = whole * scale + BigInt(fraction.padEnd(decimals, '0'));
  if (isArea && units === 0n) {
    return { units: null, error: 'A metragem deve ser maior que zero.' };
  }

  return { units, error: '' };
}

export function materialSubtotal(area, rate) {
  // Round the material line to the nearest cent, rounding half a cent up.
  return (area * rate + areaScale / 2n) / areaScale;
}

export function calculateQuote(area, rate, freight, costs) {
  const subtotal = materialSubtotal(area, rate);
  const extras = costs.reduce((sum, cost) => sum + cost.units, 0n);
  return { subtotal, extras, total: subtotal + (freight ?? 0n) + extras };
}

export function formatMoney(cents) {
  const fraction = String(cents % 100n).padStart(2, '0');
  return currencyFormatter.formatToParts(cents / 100n)
    .map(part => part.type === 'fraction' ? fraction : part.value)
    .join('');
}

export function formatArea(units) {
  const fraction = String(units % areaScale).padStart(4, '0')
    .replace(/0+$/, '').padEnd(2, '0');
  return `${wholeFormatter.format(units / areaScale)},${fraction} m²`;
}
