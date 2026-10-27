// Small, interruptible spring for the tools sheet. No network dependency.
import { containDialogFocus } from './core.js';
export function presentSheet(dialog, handle) {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  let y = reduce.matches ? 0 : 48, velocity = 0, target = 0, frame = 0, last = 0;
  let closing = false, dragging = false, start = 0, origin = 0, samples = [];
  const paint = () => { dialog.style.transform = `translateY(${y}px)`; };
  const finish = () => { if (closing) dialog.close(); };
  const tick = (now) => {
    const dt = Math.min((now - (last || now)) / 1000, 0.032);
    last = now;
    // Exact critically damped solution retains position and velocity on retarget.
    const omega = 24, x = y - target, c = velocity + omega * x, decay = Math.exp(-omega * dt);
    y = target + (x + c * dt) * decay;
    velocity = (velocity - omega * c * dt) * decay;
    paint();
    if (Math.abs(y - target) < 0.3 && Math.abs(velocity) < 5) {
      y = target; velocity = 0; frame = 0; last = 0; paint(); finish();
    } else frame = requestAnimationFrame(tick);
  };
  const moveTo = (next, dismiss = false) => {
    closing = dismiss; target = next;
    if (reduce.matches) { cancelAnimationFrame(frame); frame = 0; y = next; velocity = 0; paint(); finish(); }
    else if (!frame) { last = 0; frame = requestAnimationFrame(tick); }
  };
  const close = () => moveTo(dialog.getBoundingClientRect().height + 40, true);
  dialog.addEventListener('cancel', e => { e.preventDefault(); close(); });
  dialog.addEventListener('click', e => {
    const r = dialog.getBoundingClientRect();
    if (e.target === dialog && (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom)) close();
  });
  handle.addEventListener('pointerdown', e => {
    if (e.button !== 0) return;
    cancelAnimationFrame(frame); frame = 0; last = 0; closing = false;
    dragging = true; start = e.clientY; origin = y; samples = [[e.timeStamp, e.clientY]];
    handle.setPointerCapture(e.pointerId);
  });
  handle.addEventListener('pointermove', e => {
    if (!dragging) return;
    const next = origin + e.clientY - start;
    y = next < 0 ? next * 0.2 : next;
    samples.push([e.timeStamp, e.clientY]);
    samples = samples.filter(s => e.timeStamp - s[0] < 100);
    paint();
  });
  const end = (e, cancelled = false) => {
    if (!dragging) return;
    dragging = false;
    if (handle.hasPointerCapture(e.pointerId)) handle.releasePointerCapture(e.pointerId);
    const first = samples[0];
    velocity = !cancelled && first && e.timeStamp > first[0] ? Math.max(-1800, Math.min(1800, (e.clientY - first[1]) / (e.timeStamp - first[0]) * 1000)) : 0;
    const projected = y + velocity * 0.16;
    if (!cancelled && y > 10 && projected > dialog.getBoundingClientRect().height * 0.3) close();
    else moveTo(0);
  };
  handle.addEventListener('pointerup', e => end(e));
  handle.addEventListener('pointercancel', e => end(e, true));
  reduce.addEventListener('change', changed);
  function changed() { if (reduce.matches && !dragging) moveTo(target, closing); }
  dialog.addEventListener('close', () => { cancelAnimationFrame(frame); reduce.removeEventListener('change', changed); }, {once:true});
  containDialogFocus(dialog);
  dialog.showModal(); paint(); moveTo(0);
  return close;
}
