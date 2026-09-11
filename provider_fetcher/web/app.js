const state = {
  models: [],
  favorites: [],
  filter: "all",
  query: "",
  lastFetch: null,
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
  els.toast.classList.add("hidden");
  els.toast.innerHTML = "";
}

function showToast(title, body) {
  els.toast.innerHTML = `<strong>${escapeHtml(title)}</strong><div>${escapeHtml(body)}</div>`;
  els.toast.classList.remove("hidden");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(hideToast, 8000);
}

function currentCredential() {
  return {
    base_url: els.baseUrl.value.trim(),
    api_key: els.apiKey.value.trim(),
  };
}

function canSaveFavorite() {
  const cred = currentCredential();
  return Boolean(state.lastFetch && cred.base_url && cred.api_key);
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

function applyFetchResult(data, options = {}) {
  state.models = data.models || [];
  state.lastFetch = data;
  els.resultPanel.classList.remove("hidden");
  if (data.api_format_hint) els.apiHint.textContent = data.api_format_hint;
  if (data.base_url) els.baseUrl.value = data.base_url;
  if (options.clearKey) els.apiKey.value = "";
  els.saveFavoriteBtn.disabled = !canSaveFavorite();
  const counts = data.counts || {};
  setStatus(`拉到 ${counts.all || 0} 个模型，知识库命中 ${counts.matched || 0} 个。对话 ${counts.chat || 0} / 生图 ${counts.image || 0} / 生视频 ${counts.video || 0}。可收藏这组 URL + Key，下次再向供应商拉最新名单。`);
  renderModels();
  if (data.favorites) applyFavorites(data.favorites);
  if (options.suggestSave && data.suggest_save && canSaveFavorite()) {
    showToast("检测到新的凭据组合", "建议收藏这组 Base URL + API Key，供应商更新模型后可再查最新名单。");
  } else {
    hideToast();
  }

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  els.fetchBtn.disabled = true;
  setStatus("正在向供应商拉取模型列表…");
  try {
    const data = await api("/api/fetch", {
      method: "POST",
      body: JSON.stringify(currentCredential()),
    });
    applyFetchResult(data, { suggestSave: true });
  } catch (error) {
    setStatus(`获取失败：${error.message}`);
  } finally {
    els.fetchBtn.disabled = false;
    els.saveFavoriteBtn.disabled = !canSaveFavorite();
  }
});

els.saveFavoriteBtn.addEventListener("click", async () => {
  if (!canSaveFavorite()) return;
  els.saveFavoriteBtn.disabled = true;
  try {
    const data = await api("/api/favorites", {
      method: "POST",
      body: JSON.stringify({
        ...currentCredential(),
        last_counts: state.lastFetch?.counts || {},
      }),
    });
    applyFavorites(data.items);
    hideToast();
    setStatus("已收藏这组 Base URL + API Key。下次可直接点「再查最新」，向供应商拉取当前模型名单。");
  } catch (error) {
    setStatus(`收藏失败：${error.message}`);
  } finally {
    els.saveFavoriteBtn.disabled = !canSaveFavorite();
  }
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

els.favoriteRows.addEventListener("click", async (event) => {
  const refetch = event.target.closest("button[data-refetch]");
  if (refetch) {
    refetch.disabled = true;
    setStatus("正在用收藏的凭据向供应商拉取最新模型…");
    try {
      const data = await api("/api/favorites/refetch", {
        method: "POST",
        body: JSON.stringify({ id: refetch.dataset.refetch }),
      });
      applyFetchResult(data, { clearKey: true });
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
