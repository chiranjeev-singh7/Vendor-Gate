(() => {
  const stages = [
    ['intake', 'Intake'], ['completeness', 'Completeness'], ['tax', 'Tax ID validation'],
    ['bank', 'Bank validation'], ['names', 'Name consistency'], ['documents', 'Document check'],
    ['risk', 'Risk and duplicate checks'], ['decision', 'Decision engine'],
    ['communication', 'Communication'], ['persist', 'Persist and notify']
  ];
  const byName = new Map(stages.map(([id, name]) => [name, id]));
  window.__stageTransitions = [];
  const originalInsert = Element.prototype.insertAdjacentHTML;
  Element.prototype.insertAdjacentHTML = function (position, html) {
    if (this.id !== 'streamsteps') return originalInsert.call(this, position, html);
    const temp = document.createElement('template');
    temp.innerHTML = html;
    const incoming = temp.content.firstElementChild;
    if (!incoming) return;
    const name = incoming.querySelector('b')?.textContent || '';
    const id = byName.get(name);
    if (!id) return originalInsert.call(this, position, html);
    let row = document.getElementById(`step-${id}`);
    if (!row) {
      row = document.createElement('div');
      row.id = `step-${id}`;
      this.appendChild(row);
    }
    const spanText = incoming.querySelector('span')?.textContent || '';
    const rawState = spanText.split('·')[0].trim();
    const state = rawState === 'running' ? 'running' : 'done';
    const previous = row.dataset.state || 'idle';
    const stamp = new Date().toISOString();
    row.dataset.state = state;
    row.dataset.timestamp = stamp;
    row.title = stamp;
    row.className = 'p-3 border rounded-lg';
    row.replaceChildren();
    const title = document.createElement('b');
    title.textContent = name;
    const text = document.createElement('span');
    text.className = 'text-slate-500';
    const display = state === 'running' ? 'Running' : rawState === 'pass' ? 'Done · pass' : rawState === 'warn' ? 'Done · warning' : `Done · ${rawState}`;
    text.textContent = `${display} · ${spanText.split('·').slice(1).join('·').trim()}`;
    if (state === 'running') {
      const spinner = document.createElement('i');
      spinner.className = 'inline-block w-3 h-3 mr-1 border-2 border-blue-600 border-t-transparent rounded-full animate-spin';
      row.append(title, document.createTextNode(' '), spinner, text);
    } else row.append(title, document.createTextNode(' '), text);
    window.__stageTransitions.push({ stage_id: id, from: previous, to: state, timestamp: stamp });
  };
  const initialize = () => {
    const list = document.getElementById('streamsteps');
    if (!list || list.dataset.initialized) return;
    list.dataset.initialized = 'true';
    for (const [id, name] of stages) {
      const row = document.createElement('div');
      row.id = `step-${id}`;
      row.dataset.state = 'idle';
      row.className = 'p-3 border rounded-lg opacity-60';
      const title = document.createElement('b');
      title.textContent = name;
      const status = document.createElement('span');
      status.className = 'text-slate-500';
      status.textContent = ' Idle';
      row.append(title, status);
      list.appendChild(row);
      window.__stageTransitions.push({ stage_id: id, from: null, to: 'idle', timestamp: new Date().toISOString() });
    }
  };
  new MutationObserver(initialize).observe(document.body, { childList: true, subtree: true });
})();
