import { render } from 'solid-js/web';
import App from './App';
import './style.css';

const root = document.getElementById('root');
if (root) {
  try {
    root.replaceChildren();
    render(() => <App />, root);
  } catch {
    root.textContent = 'The tutor could not start. Rebuild with make build-web, restart make serve, and reload.';
  }
}
