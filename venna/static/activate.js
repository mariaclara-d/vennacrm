const tokenField = document.querySelector('#invitation-token');
const invitation = new URLSearchParams(location.hash.slice(1)).get('convite');
if (/^[A-Za-z0-9_-]{43}$/.test(invitation || '')) {
  tokenField.value = invitation;
  history.replaceState(null, '', location.pathname);
}
if (tokenField.value) {
  tokenField.type = 'hidden';
  document.querySelector('#token-field').hidden = true;
}
