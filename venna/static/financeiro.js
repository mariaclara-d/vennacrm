function fmt(cents) {
  const n = Number(cents);
  return 'R$ ' + (n / 100).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const modeBtns = document.querySelectorAll('.fin-mode-btn');
const splitBtns = document.querySelectorAll('.fin-split-btn');
const modeCommission = document.getElementById('mode-commission');
const modeSplit = document.getElementById('mode-split');
const commissionPct = document.getElementById('commission-pct');
const cardFee = document.getElementById('card-fee');
const filterStatus = document.getElementById('filter-status');
const calcColHeader = document.getElementById('calc-col-header');
const finResult = document.getElementById('fin-result');
const splitName3 = document.getElementById('split-name-3');

let currentMode = 'commission';
let currentParts = 2;

modeBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    modeBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentMode = btn.dataset.mode;
    modeCommission.hidden = currentMode !== 'commission';
    modeSplit.hidden = currentMode !== 'split';
    recalc();
  });
});

splitBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    splitBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentParts = parseInt(btn.dataset.parts);
    splitName3.hidden = currentParts < 3;
    recalc();
  });
});

[commissionPct, cardFee, filterStatus].forEach(el => el.addEventListener('input', recalc));
document.querySelectorAll('.split-name').forEach(el => el.addEventListener('input', recalc));

function recalc() {
  const fee = parseFloat(cardFee.value) || 0;
  const commPct = parseFloat(commissionPct.value) || 0;
  const statusFilter = filterStatus.value;

  const rows = document.querySelectorAll('#fin-table tbody tr');
  let totals = { accepted: 0, sent: 0, declined: 0 };
  let netAccepted = 0;

  rows.forEach(row => {
    const status = row.dataset.status;
    const gross = parseInt(row.dataset.total) || 0;
    const show = statusFilter === 'all' || statusFilter === status;
    row.hidden = !show;
    if (row.hidden) return;

    const cardDeduct = Math.round(gross * fee / 100);
    const afterCard = gross - cardDeduct;
    let calcVal = 0;
    let netVal = 0;

    if (currentMode === 'commission') {
      calcVal = Math.round(afterCard * commPct / 100);
      netVal = afterCard - calcVal;
    } else {
      calcVal = 0;
      netVal = afterCard;
    }

    row.querySelector('.col-card-fee').textContent = fee > 0 ? fmt(cardDeduct) : '—';
    row.querySelector('.col-calc').textContent = currentMode === 'commission' ? fmt(calcVal) : '—';
    row.querySelector('.col-net').textContent = fmt(netVal);

    totals[status] = (totals[status] || 0) + gross;
    if (status === 'accepted') netAccepted += netVal;
  });

  document.getElementById('total-accepted').textContent = fmt(totals.accepted);
  document.getElementById('total-sent').textContent = fmt(totals.sent);
  document.getElementById('total-declined').textContent = fmt(totals.declined);
  document.getElementById('total-net').textContent = fmt(netAccepted);

  calcColHeader.textContent = currentMode === 'commission' ? 'Comissão' : '—';

  if (currentMode === 'commission' && commPct > 0) {
    const grossAccepted = totals.accepted;
    const cardDeductAccepted = Math.round(grossAccepted * fee / 100);
    const commTotal = Math.round((grossAccepted - cardDeductAccepted) * commPct / 100);
    finResult.innerHTML = `<div class="fin-result-box"><strong>Comissão total (aceitos):</strong> ${fmt(commTotal)}</div>`;
  } else if (currentMode === 'split' && netAccepted > 0) {
    const names = [...document.querySelectorAll('.split-name')].slice(0, currentParts).map(i => i.value.trim() || `Pessoa ${[...document.querySelectorAll('.split-name')].indexOf(i) + 1}`);
    const perPerson = Math.floor(netAccepted / currentParts);
    const remainder = netAccepted - perPerson * currentParts;
    const lines = names.map((n, i) => `<span><strong>${n}:</strong> ${fmt(perPerson + (i === 0 ? remainder : 0))}</span>`).join('');
    finResult.innerHTML = `<div class="fin-result-box">${lines}</div>`;
  } else {
    finResult.innerHTML = '';
  }
}

recalc();
