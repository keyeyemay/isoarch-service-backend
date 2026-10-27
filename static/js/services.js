async function apiRequest(url, options = {}) {
  const response = await fetch(url, options);
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(Array.isArray(detail) ? detail.map((e) => e.msg).join("; ") : detail || "Не удалось выполнить действие");
  }
  return data;
}

function showError(target, error) {
  let notice = document.querySelector("[data-api-error]");
  if (!notice) {
    notice = document.createElement("p");
    notice.dataset.apiError = "";
    notice.setAttribute("role", "alert");
    notice.className = "api-error";
    target.insertAdjacentElement("afterend", notice);
  }
  notice.textContent = error.message;
}

document.querySelectorAll("[data-service-form]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("[type=submit]");
    button.disabled = true;
    try {
      const fields = new FormData(form);
      if (form.dataset.serviceForm === "create") {
        await apiRequest(form.action, {method: "POST", body: fields});
        location.assign(form.dataset.draftPage);
      } else {
        await apiRequest(form.action, {method: "PUT", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({description: fields.get("description"),
            delta_n15: Number(fields.get("delta_n15")), delta_c13: Number(fields.get("delta_c13"))})});
        location.assign(form.dataset.feedPage);
      }
    } catch (error) { showError(form, error); }
    finally { button.disabled = false; }
  });
});

document.querySelectorAll("[data-delete]").forEach((button) => {
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      await apiRequest(`/api/services/${button.dataset.delete}`, {method: "DELETE"});
      location.reload();
    } catch (error) { showError(button, error); button.disabled = false; }
  });
});

document.querySelectorAll("[data-like]").forEach((button) => {
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const like = Number(button.dataset.liked) === 1 ? 0 : 1;
      const data = await apiRequest(`/api/services/${button.dataset.like}/like`, {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({like})});
      button.dataset.liked = String(data.like);
      document.querySelector("[data-like-count]").textContent = data.likes_count;
    } catch (error) { showError(button, error); }
    finally { button.disabled = false; }
  });
});

document.querySelectorAll("[data-next]").forEach((link) => {
  link.addEventListener("click", async (event) => {
    event.preventDefault();
    try {
      const data = await apiRequest(link.dataset.nextUrl);
      location.assign(link.dataset.feedBase.replace(/\/0$/, `/${data.id}`));
    } catch (error) { showError(link, error); }
  });
});
