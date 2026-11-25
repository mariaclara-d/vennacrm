const modal = document.getElementById('modal-tarefa');
document.getElementById('btn-nova-tarefa').addEventListener('click', () => { modal.hidden = false; });
document.getElementById('btn-cancelar').addEventListener('click', () => { modal.hidden = true; });
modal.addEventListener('click', e => { if (e.target === modal) modal.hidden = true; });
