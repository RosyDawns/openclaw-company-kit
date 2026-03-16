function createBus() {
  const listeners = new Map();

  function on(event, handler) {
    if (!listeners.has(event)) listeners.set(event, new Set());
    listeners.get(event).add(handler);
  }

  function off(event, handler) {
    const set = listeners.get(event);
    if (set) set.delete(handler);
  }

  function emit(event, data) {
    const set = listeners.get(event);
    if (set) set.forEach((fn) => fn(data));
  }

  return { on, off, emit };
}

export const panelBus = createBus();
