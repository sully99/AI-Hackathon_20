const STORAGE_KEY = 'fitnote_profile_v1';
const form = document.querySelector('#profile-form');
const savedPanel = document.querySelector('#saved-profile');
const statusBox = document.querySelector('#profile-status');
const errorBox = document.querySelector('#profile-error');
const title = document.querySelector('#wardrobe-title');
const fields = [['length_cm', '총장'], ['shoulder_cm', '어깨'], ['chest_width_cm', '가슴'], ['sleeve_cm', '소매']];
let busy = false;
let blockedUntil = 0;

function element(name, text, className) {
  const el = document.createElement(name);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function setBusy(value) {
  busy = value;
  document.querySelectorAll('input, button, select').forEach(el => el.disabled = value);
}

function readLocalProfile() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.clothes) || !parsed.clothes.length) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeLocalProfile(profile) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
}

function fillForm(profile) {
  const clothes = profile?.clothes || [];
  [1, 2, 3].forEach(n => {
    const item = clothes[n - 1];
    const isPreset = item?.product?.product_name?.startsWith('[실측기준]');
    document.querySelector(`#url-${n}`).value = (item && !isPreset) ? (item.product?.source_url || '') : '';
    document.querySelector(`#size-${n}`).value = (item && !isPreset) ? (item.size || '') : '';
  });
}

function renderSaved(profile) {
  const list = document.querySelector('#saved-clothes');
  list.replaceChildren();
  for (const item of profile.clothes) {
    const row = element('div', undefined, 'saved-item');
    const name = element('strong', item.product?.product_name || '등록한 기준 옷');
    const badge = element('span', item.size, 'tag');
    const summary = fields
      .filter(([key]) => item.measurements?.[key] != null)
      .map(([key, label]) => `${label} ${item.measurements[key]}cm`)
      .join(' · ');
    row.append(name, badge, element('p', summary, 'hint'));
    list.append(row);
  }
  const traits = fields
    .filter(([key]) => profile.measurement_preferences?.[key])
    .map(([key, label]) => {
      const t = profile.measurement_preferences[key];
      return `${label} ${t.min}~${t.max}cm (평균 ${t.average}cm)`;
    })
    .join(' · ');
  document.querySelector('#saved-traits').textContent = traits || '실측 범위 정보 없음';
}

function showForm(profile) {
  fillForm(profile);
  savedPanel.hidden = true;
  form.hidden = false;
  title.textContent = '잘 맞는 기준 옷 등록.';
  statusBox.textContent = '내 기기에만 저장되며 다른 사용자와 섞이지 않아요.';
}

async function submitProfile(payload) {
  if (busy) return;
  if (Date.now() < blockedUntil) {
    showError(`무신사 요청 제한 대기 중입니다. ${Math.ceil((blockedUntil - Date.now()) / 1000)}초 후 다시 시도해 주세요.`);
    return;
  }
  errorBox.hidden = true;
  setBusy(true);
  statusBox.textContent = '기준 옷의 실측표를 불러오고 있어요…';
  try {
    const response = await fetch('/api/profile', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Page-Token': document.querySelector('meta[name="page-token"]').content,
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (response.status === 429 && data.retry_after) blockedUntil = Date.now() + data.retry_after * 1000;
    if (!response.ok) throw new Error(data.error || '기준 옷을 저장하지 못했어요.');
    writeLocalProfile(data.profile);
    window.location.assign('/compare');
  } catch (error) {
    showError(error.message);
    statusBox.textContent = '';
  } finally {
    setBusy(false);
  }
}

form.addEventListener('submit', event => {
  event.preventDefault();
  const clothes = [1, 2, 3]
    .map(n => ({
      url: document.querySelector(`#url-${n}`).value.trim(),
      size: document.querySelector(`#size-${n}`).value.trim(),
    }))
    .filter(x => x.url || x.size);
  if (!clothes.length) {
    showError('무신사 상품 링크와 사이즈를 1벌 이상 입력하거나, 아래 대표 실측표를 선택해 주세요.');
    return;
  }
  submitProfile({clothes});
});

document.querySelector('#apply-preset')?.addEventListener('click', () => {
  const preset_brand = document.querySelector('#preset-brand').value;
  const preset_size = document.querySelector('#preset-size').value;
  submitProfile({preset_brand, preset_size});
});

document.querySelector('#edit-profile')?.addEventListener('click', () => {
  errorBox.hidden = true;
  showForm(readLocalProfile());
});

function init() {
  const profile = readLocalProfile();
  if (profile) {
    renderSaved(profile);
    savedPanel.hidden = false;
    form.hidden = true;
    title.textContent = '내 기준 옷이 준비됐어요.';
    statusBox.textContent = '';
  } else {
    showForm(null);
  }
}

init();
