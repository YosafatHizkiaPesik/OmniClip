// Titik masuk iframe kotak pasir pratinjau Montase (pratinjau.html).
// Tanpa StrictMode: render ganda di mode pengembangan membuat delayRender
// komponen animasi terpanggil dua kali, dan satu di antaranya tidak pernah
// dilepas.
import { createRoot } from 'react-dom/client';
import IsiPratinjau from './features/montase/pratinjau/IsiPratinjau.jsx';

createRoot(document.getElementById('pratinjau')).render(<IsiPratinjau />);
