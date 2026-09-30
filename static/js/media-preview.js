// Локальный предпросмотр; оба файла отправляются в REST API через FormData.
document.querySelectorAll("input[data-preview]").forEach((input) => {
  const preview = document.getElementById(input.dataset.preview);
  const defaultSource = preview.src;
  const fallback = preview.onerror;
  let objectUrl;
  input.addEventListener("change", () => {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = input.files[0] ? URL.createObjectURL(input.files[0]) : undefined;
    preview.onerror = fallback;
    preview.src = objectUrl || defaultSource;
    if (preview.tagName === "VIDEO") preview.load();
  });
  window.addEventListener("pagehide", () => {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  });
});
