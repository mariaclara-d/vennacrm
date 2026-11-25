import { formatMoney, materialSubtotal, parseAmount } from './calculation.js';

const form = document.querySelector('#quote-form');
const items = document.querySelector('#items');
const template = document.querySelector('#item-template');
const addItem = document.querySelector('#add-item');
const subtotalOutput = document.querySelector('#subtotal');
const freightOutput = document.querySelector('#freight-summary');
const totalOutput = document.querySelector('#total');
const totalLabel = document.querySelector('#total-label');
const hint = document.querySelector('#quote-hint');
const empty = '—';
const maxLines = 40;

function formatMoneyText(cents) {
  const c = BigInt(cents);
  const whole = c / 100n;
  const frac = String(c % 100n).padStart(2, '0');
  return `R$ ${whole.toLocaleString('pt-BR')},${frac}`;
}

function buildWhatsAppText({ quoteNumber, customer, city, itemRows, subtotal, freight, total, validUntil, payment, delivery }) {
  const lines = [`\uD83D\uDCCB *Simulação VENNA*`];
  if (customer) lines.push(`Cliente: ${customer}${city ? ' · ' + city : ''}`);
  lines.push('');
  for (const item of itemRows) {
    const qty = item.unit === 'm²'
      ? `${(Number(item.quantity) / 10000).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 })} m²`
      : `${(Number(item.quantity) / 10000).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} un`;
    lines.push(`• ${item.description} – ${qty} × ${formatMoneyText(item.rate)} = ${formatMoneyText(item.total)}`);
  }
  lines.push('');
  lines.push(`Subtotal: ${formatMoneyText(subtotal)}`);
  lines.push(freight !== '' && freight !== null ? `Frete: ${formatMoneyText(freight)}` : 'Frete: A confirmar');
  lines.push(`*Total: ${formatMoneyText(total)}*`);
  if (validUntil) lines.push(`\nValidade: ${validUntil}`);
  if (payment) lines.push(`Pagamento: ${payment}`);
  if (delivery) lines.push(`Entrega: ${delivery}`);
  return lines.join('\n');
}

function copyToClipboard(text, button) {
  navigator.clipboard.writeText(text).then(() => {
    const original = button.textContent;
    button.textContent = 'Copiado!';
    button.disabled = true;
    setTimeout(() => { button.textContent = original; button.disabled = false; }, 2200);
  }).catch(() => {
    alert('Não foi possível copiar. Tente novamente.');
  });
}

// Simulador: lê os campos do formulário em tempo real
if (form) {
  function update() {
    const rows = [...items.children];
    let subtotal = 0n;
    let complete = true;
    for (const row of rows) {
      const quantity = parseAmount(row.querySelector('[name="quantity"]').value, 'area');
      const rate = parseAmount(row.querySelector('[name="rate"]').value, 'money');
      const valid = quantity.units !== null && rate.units !== null;
      const amount = valid ? materialSubtotal(quantity.units, rate.units) : null;
      row.querySelector('[data-line-total]').textContent = valid ? formatMoney(amount) : empty;
      row.querySelector('[data-remove]').disabled = rows.length === 1;
      complete = complete && valid;
      subtotal += amount ?? 0n;
    }
    const freight = parseAmount(form.elements.freight.value, 'money', true);
    const hasFreight = freight.units !== null;
    subtotalOutput.textContent = complete ? formatMoney(subtotal) : empty;
    freightOutput.textContent = freight.error ? 'Valor inválido' : hasFreight ? formatMoney(freight.units) : 'A confirmar';
    totalLabel.textContent = hasFreight ? 'Valor total' : 'Total sem frete';
    totalOutput.textContent = complete && !freight.error ? formatMoney(subtotal + (freight.units ?? 0n)) : empty;
    hint.textContent = !complete ? 'Preencha a quantidade e o preço de cada item.'
      : freight.error ? 'Confira o valor do frete.'
      : hasFreight ? 'Estimativa com os valores informados.' : 'Frete a confirmar.';
    addItem.disabled = rows.length >= maxLines;
  }

  form.addEventListener('input', update);
  addItem.addEventListener('click', () => {
    items.append(template.content.cloneNode(true));
    items.lastElementChild.querySelector('input').focus();
    update();
  });
  items.addEventListener('click', event => {
    const button = event.target.closest('[data-remove]');
    if (!button || items.children.length <= 1) return;
    const row = button.closest('[data-item]');
    const adjacent = row.nextElementSibling || row.previousElementSibling;
    row.remove();
    adjacent.querySelector('input').focus();
    update();
  });
  update();

  const copyBtn = document.querySelector('#copy-whatsapp');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const rows = [...items.children].map(row => {
        const desc = row.querySelector('[name="description"]').value.trim();
        const unit = row.querySelector('[name="unit"]').value;
        const qty = parseAmount(row.querySelector('[name="quantity"]').value, 'area');
        const rate = parseAmount(row.querySelector('[name="rate"]').value, 'money');
        if (!desc || qty.units === null || rate.units === null) return null;
        const total = materialSubtotal(qty.units, rate.units);
        return { description: desc, unit, quantity: String(qty.units), rate: String(rate.units), total: String(total) };
      }).filter(Boolean);
      if (!rows.length) { alert('Preencha ao menos um item para copiar.'); return; }
      const freightParsed = parseAmount(form.elements.freight.value, 'money', true);
      const subtotal = rows.reduce((s, r) => s + BigInt(r.total), 0n);
      const freight = freightParsed.units !== null ? String(freightParsed.units) : '';
      const total = subtotal + (freightParsed.units ?? 0n);
      const leadSelect = form.elements.lead_id;
      const customerName = leadSelect ? leadSelect.options[leadSelect.selectedIndex]?.text.split(' ·')[0] : '';
      const validInput = form.elements.valid_until?.value;
      const validLabel = validInput ? new Date(validInput + 'T12:00:00').toLocaleDateString('pt-BR') : '';
      const text = buildWhatsAppText({
        customer: customerName,
        city: '',
        itemRows: rows,
        subtotal: String(subtotal),
        freight,
        total: String(total),
        validUntil: validLabel,
        payment: form.elements.payment?.value.trim() || '',
        delivery: form.elements.delivery?.value.trim() || '',
      });
      copyToClipboard(text, copyBtn);
    });
  }
}

// Página do orçamento salvo: lê dados dos data attributes
const savedCopyBtn = document.querySelector('#copy-whatsapp[data-quote]');
if (savedCopyBtn) {
  savedCopyBtn.addEventListener('click', () => {
    const d = savedCopyBtn.dataset;
    const itemRows = JSON.parse(d.items);
    const text = buildWhatsAppText({
      quoteNumber: d.quote,
      customer: d.customer,
      city: d.city,
      itemRows,
      subtotal: d.subtotal,
      freight: d.freight,
      total: d.total,
      validUntil: d.valid,
      payment: d.payment,
      delivery: d.delivery,
    });
    copyToClipboard(text, savedCopyBtn);
  });
}
