const csrf = document.getElementById('csrf-token').value;
let dragged = null;

document.querySelectorAll('.kanban-card').forEach(card => {
  card.addEventListener('dragstart', e => {
    dragged = card;
    card.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
  });
  card.addEventListener('dragend', () => {
    card.classList.remove('dragging');
    dragged = null;
  });
});

document.querySelectorAll('.kanban-cards').forEach(col => {
  col.addEventListener('dragover', e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    col.classList.add('drag-over');
  });
  col.addEventListener('dragleave', () => col.classList.remove('drag-over'));
  col.addEventListener('drop', async e => {
    e.preventDefault();
    col.classList.remove('drag-over');
    if (!dragged) return;
    const newStage = col.dataset.stage;
    const leadId = dragged.dataset.leadId;
    const oldCol = dragged.closest('.kanban-cards');
    if (oldCol === col) return;

    col.appendChild(dragged);
    updateCount(oldCol);
    updateCount(col);

    await fetch(`/kanban/${leadId}/stage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `csrf_token=${encodeURIComponent(csrf)}&stage=${encodeURIComponent(newStage)}`,
    });
  });
});

function updateCount(colCards) {
  const header = colCards.closest('.kanban-col').querySelector('.kanban-col-count');
  if (header) header.textContent = colCards.children.length;
}
