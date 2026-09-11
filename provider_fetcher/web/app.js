const state = {
  models: [],
  favorites: [],
  filter: "all",
  query: "",
  lastFetch: null,
  lastCredential: null,
};

const els = {
  form: document.getElementById("fetchForm"),
  baseUrl: document.getElementById("baseUrl"),
  apiKey: document.getElementById("apiKey"),
  fetchBtn: document.getElementById("fetchBtn"),
  saveFavoriteBtn: document.getElementById("saveFavoriteBtn"),
  refreshCatalogBtn: document.getElementById("refreshCatalogBtn"),
  statusLine: document.getElementById("statusLine"),
  apiHint: document.getElementById("apiHint"),
  resultPanel: document.getElementById("resultPanel"),
  modelRows: document.getElementById("modelRows"),
  favoriteRows: document.getElementById("favoriteRows"),
  search: document.getElementById("search"),
  toast: document.getElementById("toast"),
  nameDialog: document.getElementById("nameDialog"),
  nameForm: document.getElementById("nameForm"),
  favoriteName: document.getElementById("favoriteName"),
  nameCancelBtn: document.getElementById("nameCancelBtn"),
};

let toastTimer = 0;

function formatNumber(value) {
  return typeof value === "number" ? value.toLocaleString("en-US") : "—";
}

function inputsHtml(inputs) {
  if (!inputs || !inputs.length) return "—";
  return inputs.map((item) => `<span class="badge">${item}</span>`).join("");
}

function kindLabel(kind) {
  if (kind === "image") return "生图";
  if (kind === "video") return "生视频";
  return "对话";
}

function setStatus(text) {
  els.statusLine.textContent = text;
}

function hideToast() {
  window.clearTimeout(toastTimer);
  els.toast.classList.add("hidden");
  els.toast.innerHTML = "";
}

function showSaveToast() {
  els.toast.innerHTML = `
    <strong>检测到新的凭据组合</strong>
    <p>建议收藏并命名这组 Base URL + API Key，供应商更新模型后可再查最新名单。</p>
    <div class="toast-actions">
      <button type="button" id="toastSaveBtn">命名并收藏</button>
      <button type="button" id="toastDismissBtn" class="ghost">稍后</button>
    </div>
  `;
  els.toast.classList.remove("hidden");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(hideToast, 12000);
}

function currentCredential() {
  return {
    base_url: els.baseUrl.value.trim(),
    api_key: els.apiKey.value.trim(),
  };
}

function credentialToSave() {
  if (state.lastCredential?.base_url && state.lastCredential?.api_key) {
    return state.lastCredential;
  }
  return currentCredential();
}

function canSaveFavorite() {
  const cred = credentialToSave();
  return Boolean(state.lastFetch && cred.base_url && cred.api_key);
}

function defaultFavoriteName() {
  const cred = credentialToSave();
  try {
    return new URL(cred.base_url).host;
  } catch {
    return cred.base_url || "未命名凭据";
  }
}

async function api(path, options) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `HTTP_${response.status}`);
  }
  return data;
}

function renderModels() {
  const rows = state.models.filter((row) => {
    if (state.filter !== "all" && row.kind !== state.filter) return false;
    if (state.query && !row.id.toLowerCase().includes(state.query)) return false;
    return true;
  });
  if (!rows.length) {
    els.modelRows.innerHTML = `<tr><td colspan="5" class="empty">没有匹配的模型。</td></tr>`;
    return;
  }
  els.modelRows.innerHTML = rows.map((row) => `
    <tr>
      <td>
        <div>${escapeHtml(row.id)}</div>
        <div class="kind">${kindLabel(row.kind)}</div>
        ${row.notes?.length ? `<div class="note">${escapeHtml(row.notes.join("；"))}</div>` : ""}
      </td>
      <td>${formatNumber(row.context)}</td>
      <td>${formatNumber(row.max_output)}</td>
      <td>${inputsHtml(row.inputs)}</td>
      <td>${escapeHtml(row.source)}</td>
    </tr>
  `).join("");
}

function countsText(counts) {
  if (!counts || !counts.all) return "尚未再次拉取";
  return `${counts.all} 个模型（对话 ${counts.chat || 0} / 生图 ${counts.image || 0} / 生视频 ${counts.video || 0}）`;
}

function renderFavorites() {
  if (!state.favorites.length) {
    els.favoriteRows.innerHTML = `<tr><td colspan="5" class="empty">还没有收藏凭据。</td></tr>`;
    return;
  }
  els.favoriteRows.innerHTML = state.favorites.map((row) => `
    <tr>
      <td>${escapeHtml(row.label || row.host || "")}</td>
      <td>${escapeHtml(row.base_url || "")}</td>
      <td>${escapeHtml(row.api_key_masked || "")}</td>
      <td>
        <div>${escapeHtml(row.last_fetched_at || row.saved_at || "")}</div>
        <div class="kind">${escapeHtml(countsText(row.last_counts))}</div>
      </td>
      <td>
        <button type="button" class="ghost" data-refetch="${escapeAttr(row.id)}">再查最新</button>
        <button type="button" class="link" data-unfav="${escapeAttr(row.id)}">移除</button>
      </td>
    </tr>
  `).join("");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll('"', "&quot;");
}

function applyFavorites(items) {
  state.favorites = items || [];
  renderFavorites();
}

function openNameDialog() {
  if (!canSaveFavorite()) return;
  els.favoriteName.value = defaultFavoriteName();
  els.nameDialog.classList.remove("hidden");
  els.favoriteName.focus();
  els.favoriteName.select();
}

function closeNameDialog() {
  els.nameDialog.classList.add("hidden");
}

function applyFetchResult(data, options = {}) {
  state.models = data.models || [];
  state.lastFetch = data;
  if (options.credential) state.lastCredential = options.credential;
  els.resultPanel.classList.remove("hidden");
  if (data.api_format_hint) els.apiHint.textContent = data.api_format_hint;
  if (data.base_url) els.baseUrl.value = data.base_url;
  if (options.clearKey) els.apiKey.value = "";
  els.saveFavoriteBtn.disabled = !canSaveFavorite();
  const counts = data.counts || {};
  const alreadySaved = data.already_saved === true;
  const suggestSave = options.suggestSave && data.suggest_save === true && !alreadySaved && canSaveFavorite();
  if (alreadySaved) {
    setStatus(`拉到 ${counts.all || 0} 个模型，知识库命中 ${counts.matched || 0} 个。这组凭据已收藏，可在下方直接再查最新。`);
  } else {
    setStatus(`拉到 ${counts.all || 0} 个模型，知识库命中 ${counts.matched || 0} 个。对话 ${counts.chat || 0} / 生图 ${counts.image || 0} / 生视频 ${counts.video || 0}。`);
  }
  renderModels();
  if (data.favorites) applyFavorites(data.favorites);
  if (suggestSave) showSaveToast();
  else hideToast();
}

async function saveFavorite(label) {
  const cred = credentialToSave();
  const data = await api("/api/favorites", {
    method: "POST",
    body: JSON.stringify({
      ...cred,
      label,
      last_counts: state.lastFetch?.counts || {},
    }),
  });
  applyFavorites(data.items);
  if (state.lastFetch) {
    state.lastFetch.already_saved = true;
    state.lastFetch.suggest_save = false;
  }
  hideToast();
  closeNameDialog();
  setStatus(`已收藏「${label}」。下次可直接点「再查最新」，向供应商拉取当前模型名单。`);
}

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  els.fetchBtn.disabled = true;
  setStatus("正在向供应商拉取模型列表…");
  const credential = currentCredential();
  try {
    const data = await api("/api/fetch", {
      method: "POST",
      body: JSON.stringify(credential),
    });
    applyFetchResult(data, { suggestSave: true, credential });
  } catch (error) {
    setStatus(`获取失败：${error.message}`);
  } finally {
    els.fetchBtn.disabled = false;
    els.saveFavoriteBtn.disabled = !canSaveFavorite();
  }
});

els.saveFavoriteBtn.addEventListener("click", () => {
  openNameDialog();
});

els.refreshCatalogBtn.addEventListener("click", async () => {
  els.refreshCatalogBtn.disabled = true;
  setStatus("正在更新 models.dev 知识库…");
  try {
    const data = await api("/api/catalog/refresh", { method: "POST", body: "{}" });
    setStatus(`知识库已更新：${data.catalog_fetched_at || "完成"}`);
  } catch (error) {
    setStatus(`知识库更新失败：${error.message}`);
  } finally {
    els.refreshCatalogBtn.disabled = false;
  }
});

document.getElementById("filters").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-filter]");
  if (!button) return;
  state.filter = button.dataset.filter;
  document.querySelectorAll("#filters .chip").forEach((chip) => chip.classList.toggle("active", chip === button));
  renderModels();
});

els.search.addEventListener("input", () => {
  state.query = els.search.value.trim().toLowerCase();
  renderModels();
});

els.baseUrl.addEventListener("input", () => {
  els.saveFavoriteBtn.disabled = !canSaveFavorite();
});
els.apiKey.addEventListener("input", () => {
  els.saveFavoriteBtn.disabled = !canSaveFavorite();
});

els.toast.addEventListener("click", (event) => {
  if (event.target.id === "toastSaveBtn") {
    hideToast();
    openNameDialog();
  }
  if (event.target.id === "toastDismissBtn") hideToast();
});

els.nameCancelBtn.addEventListener("click", () => closeNameDialog());
els.nameDialog.addEventListener("click", (event) => {
  if (event.target === els.nameDialog) closeNameDialog();
});
els.nameForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const label = els.favoriteName.value.trim();
  if (!label) return;
  try {
    await saveFavorite(label);
  } catch (error) {
    setStatus(`收藏失败：${error.message}`);
  }
});

els.favoriteRows.addEventListener("click", async (event) => {
  const refetch = event.target.closest("button[data-refetch]");
  if (refetch) {
    refetch.disabled = true;
    setStatus("正在用收藏的凭据向供应商拉取最新模型…");
    try {
      const favorite = state.favorites.find((item) => item.id === refetch.dataset.refetch);
      const data = await api("/api/favorites/refetch", {
        method: "POST",
        body: JSON.stringify({ id: refetch.dataset.refetch }),
      });
      applyFetchResult(data, {
        clearKey: true,
        suggestSave: false,
        credential: favorite ? { base_url: favorite.base_url, api_key: "" } : null,
      });
    } catch (error) {
      setStatus(`再查失败：${error.message}`);
    } finally {
      refetch.disabled = false;
    }
    return;
  }
  const unfav = event.target.closest("button[data-unfav]");
  if (!unfav) return;
  const data = await api("/api/favorites/remove", {
    method: "POST",
    body: JSON.stringify({ id: unfav.dataset.unfav }),
  });
  applyFavorites(data.items);
});

(async function boot() {
  try {
    const data = await api("/api/state");
    els.apiHint.textContent = data.api_format_hint || els.apiHint.textContent;
    applyFavorites(data.favorites || []);
    if (data.last_fetch?.models) {
      state.models = data.last_fetch.models;
      state.lastFetch = data.last_fetch;
      els.baseUrl.value = data.last_fetch.base_url || "";
      els.resultPanel.classList.remove("hidden");
      renderModels();
    }
    els.saveFavoriteBtn.disabled = !canSaveFavorite();
    const catalog = data.catalog_fetched_at ? `知识库缓存于 ${data.catalog_fetched_at}` : "本地还没有知识库缓存，可先获取模型，或点更新知识库。";
    setStatus(catalog);
  } catch (error) {
    setStatus(`启动失败：${error.message}`);
  }
})();
