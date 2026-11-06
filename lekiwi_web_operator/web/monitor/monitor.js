import { createRawEvents } from "./raw-events.js";

// Actual storage is the default. Fixtures load only after explicit DEMO selection.
const live = createRawEvents(document.getElementById("rawApp"));
let mode = "live";
let demo = null;
async function selectMode(next) {
  mode = next;
  const isLive = mode === "live";
  document
    .getElementById("liveMode")
    .setAttribute("aria-pressed", String(isLive));
  document
    .getElementById("demoMode")
    .setAttribute("aria-pressed", String(!isLive));
  document.getElementById("rawApp").hidden = !isLive;
  document.getElementById("app").hidden = isLive;
  document.getElementById("demoBanner").hidden = isLive;
  document.getElementById("modeNote").textContent = isLive
    ? "실제 수집 원본 · CORE 미연결"
    : "합성 Alert 13개 · 실제 평가 결과 아님";
  if (isLive) {
    live.activate();
    return;
  }
  live.deactivate();
  if (!demo) {
    const [{ createDashboard }, { createMockAdapter }, { response }] =
      await Promise.all([
        import("./dashboard-ui.js"),
        import("./mock-adapter.js"),
        import("./fixtures.js"),
      ]);
    if (!demo) {
      demo = createDashboard(createMockAdapter(response), document, "mock");
      demo.load(demo.state.query, null);
    }
  }
}
for (const [id, value] of [
  ["liveMode", "live"],
  ["demoMode", "demo"],
])
  document.getElementById(id).addEventListener("click", () => {
    selectMode(value).catch(() => {
      document.getElementById("modeNote").textContent =
        "데모 화면을 불러오지 못했습니다.";
    });
  });
window.addEventListener("pagehide", () => live.deactivate());
window.addEventListener("pageshow", () => {
  if (mode === "live") live.activate();
});
live.activate();
