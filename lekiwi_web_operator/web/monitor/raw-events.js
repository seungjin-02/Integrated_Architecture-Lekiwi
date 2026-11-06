import {
  displayTime,
  eventPath,
  eventQuery,
  validateEvent,
  validatePage,
} from "./raw-contract.js";

export function createRawEvents(
  root,
  fetcher = globalThis.fetch.bind(globalThis),
) {
  const document = root.ownerDocument;
  const element = (tag, content, className, id) => {
    const node = document.createElement(tag);
    if (content !== undefined) node.textContent = content;
    if (className) node.className = className;
    if (id) node.id = id;
    return node;
  };
  const mast = element("header", undefined, "mast");
  mast.append(element("div", "XLeRobot 로그 운영 시스템", "identity"));
  const connection = element("div", undefined, "mast-right");
  connection.append(
    element("span", "로컬 원본", "environment"),
    element("span", "CORE 미연결", "small"),
  );
  mast.append(connection);
  const main = element("main", undefined, "dashboard raw-monitor");
  const head = element("header", undefined, "workspace-head");
  const title = element("div");
  title.append(
    element("p", "XLeRobot / RAW EVENTS", "eyebrow"),
    element("h1", "원본 운영 이벤트"),
  );
  const health = element(
    "p",
    "수집 상태 확인 중",
    "small raw-health",
    "rawHealth",
  );
  health.setAttribute("role", "status");
  head.append(title, health);
  const queryShell = element("section", undefined, "query-shell");
  queryShell.setAttribute("aria-label", "원본 이벤트 조회");
  queryShell.append(element("h2", "조회 조건"));
  const form = element("form", undefined, "query-form", "rawQuery");
  form.noValidate = true;
  const grid = element("div", undefined, "query-grid raw-query-grid");
  const controls = {};
  for (const [name, label, type, value, placeholder] of [
    ["limit", "요청당 조회 개수", "text", "50", "1~100"],
    ["source", "이벤트 출처 · source", "text", "", "전체 출처"],
    ["trace_id", "흐름 식별자 · trace_id", "text", "", "전체 흐름"],
    ["since", "발생 시작 · KST", "datetime-local", "", ""],
    ["until", "발생 종료 · KST", "datetime-local", "", ""],
  ]) {
    const field = element("div", undefined, "filter");
    const input = element("input", undefined, undefined, `raw-${name}`);
    input.name = name;
    input.type = type;
    input.value = value;
    input.placeholder = placeholder;
    if (name === "limit") input.inputMode = "numeric";
    if (type === "text") input.maxLength = 256;
    else input.step = "1";
    const caption = element("label", label);
    caption.htmlFor = input.id;
    input.setAttribute("aria-describedby", "rawQueryError");
    field.append(caption, input);
    grid.append(field);
    controls[name] = input;
  }
  const queryActions = element("div", undefined, "query-actions");
  const submit = element("button", "조회 · 새로고침");
  submit.type = "submit";
  const reset = element("button", "필터 초기화", "filter-reset");
  reset.type = "button";
  queryActions.append(submit, reset);
  const queryError = element("p", "", "input-error", "rawQueryError");
  queryError.setAttribute("role", "alert");
  const applied = element("p", "", "applied-query", "rawAppliedQuery");
  form.append(grid, queryActions, queryError, applied);
  queryShell.append(form);

  const split = element("div", undefined, "split raw-split");
  const master = element("section", undefined, "master");
  const heading = element("header", undefined, "master-head");
  const headingLine = element("div", undefined, "list-heading");
  headingLine.append(
    element("h2", "원본 이벤트 목록"),
    element("span", "저장 순서 · 오래된 순", "small"),
  );
  heading.append(headingLine);
  const guide = element("div", undefined, "master-guide raw-guide");
  for (const caption of [
    "발생 시각 · KST",
    "출처",
    "단계 · 이벤트 식별자",
    "기록된 결과",
    "",
  ])
    guide.append(element("span", caption));
  guide.setAttribute("aria-hidden", "true");
  const rows = element("div", undefined, "inbox-list", "rawRows");
  rows.setAttribute("aria-live", "polite");
  const pagination = element("div", undefined, "query-actions raw-pagination");
  const count = element("span", "0건", "page-count", "rawCount");
  const more = element("button", "더보기", undefined, "rawMore");
  more.type = "button";
  more.hidden = true;
  pagination.append(count, more);
  master.append(heading, guide, rows, pagination);
  const inspector = element(
    "aside",
    undefined,
    "inspector raw-inspector",
    "rawInspector",
  );
  inspector.hidden = true;
  inspector.setAttribute("aria-label", "선택한 원본 이벤트");
  const detailHead = element("div", undefined, "inspector-head");
  const detailTitle = element("h2", "원본 이벤트 상세");
  detailTitle.tabIndex = -1;
  const close = element("button", "닫기", "view-action");
  close.type = "button";
  detailHead.append(detailTitle, close);
  const detailBody = element("div", undefined, undefined, "rawDetail");
  inspector.append(detailHead, detailBody);
  split.append(master, inspector);
  main.append(head, queryShell, split);
  root.replaceChildren(mast, main);

  let active = false,
    generation = 0,
    detailGeneration = 0,
    cursor = null;
  let events = [],
    selected = null,
    appliedDraft = null;
  const pending = new Set();
  async function get(path) {
    const controller = new AbortController();
    pending.add(controller);
    const timer = setTimeout(() => controller.abort(), 4000);
    try {
      const response = await fetcher(path, {
        method: "GET",
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok)
        throw Error(`원본 조회에 실패했습니다. (${response.status})`);
      return await response.json();
    } finally {
      clearTimeout(timer);
      pending.delete(controller);
    }
  }
  const draft = () =>
    Object.fromEntries(
      Object.entries(controls).map(([key, input]) => [key, input.value]),
    );
  function message(text, error = false) {
    const node = element("p", text, "state-message");
    node.setAttribute("role", error ? "alert" : "status");
    rows.replaceChildren(node);
  }
  function renderRows() {
    rows.replaceChildren();
    if (!events.length) {
      message("수집된 원본 이벤트가 없습니다.");
      return;
    }
    for (const event of events) {
      const row = element("article", undefined, "inbox-row raw-row");
      row.classList.toggle("selected", selected === event.event_id);
      const time = element("time", displayTime(event.occurred_at), "row-time");
      time.dateTime = event.occurred_at;
      const source = element("span", event.source, "mono raw-source");
      const summary = element("div", undefined, "inbox-main");
      summary.append(
        element("p", event.stage, "inbox-summary"),
        element("span", event.event_id, "mono quiet"),
      );
      const outcome = element("span", event.outcome, "mono raw-outcome");
      const view = element("button", "상세", "view-action");
      view.type = "button";
      view.setAttribute("aria-label", `${event.event_id} 원본 상세`);
      view.addEventListener("click", () => selectEvent(event.event_id, view));
      row.append(time, source, summary, outcome, view);
      rows.append(row);
    }
  }
  function renderDetail(event) {
    detailBody.replaceChildren();
    const facts = element("dl", undefined, "raw-facts");
    for (const [key, label] of [
      ["event_id", "이벤트 ID"],
      ["record_id", "저장 순번"],
      ["source", "출처"],
      ["run_id", "실행 ID"],
      ["sequence", "출처 순번"],
      ["stage", "단계"],
      ["outcome", "기록된 결과"],
      ["occurred_at", "발생 시각"],
      ["observed_at", "수집 시각"],
      ["trace_id", "흐름 ID"],
      ["command_id", "명령 ID"],
      ["reason_code", "원문 사유 코드"],
    ]) {
      const value = event[key];
      facts.append(
        element("dt", label),
        element(
          "dd",
          value == null
            ? "—"
            : key.endsWith("_at")
              ? displayTime(value)
              : String(value),
        ),
      );
    }
    const details = element("details", undefined, "raw-json");
    details.open = true;
    details.append(
      element("summary", "원본 JSON"),
      element("pre", event.raw_json ?? JSON.stringify(event, null, 2)),
    );
    detailBody.append(facts, details);
  }
  async function selectEvent(id, opener) {
    const mine = ++detailGeneration;
    selected = id;
    inspector.hidden = false;
    detailBody.replaceChildren(
      element("p", "원본을 불러오는 중입니다.", "small"),
    );
    detailTitle.focus();
    renderRows();
    try {
      const event = validateEvent(await get(eventPath(id)));
      if (!active || mine !== detailGeneration) return;
      if (event.event_id !== id)
        throw Error("요청한 원본과 응답 식별자가 다릅니다.");
      renderDetail(event);
    } catch (error) {
      if (active && mine === detailGeneration)
        detailBody.replaceChildren(
          element(
            "p",
            error.message || "원본 조회에 실패했습니다.",
            "input-error",
          ),
        );
    }
    close.onclick = () => {
      ++detailGeneration;
      selected = null;
      inspector.hidden = true;
      renderRows();
      if (opener?.isConnected) opener.focus();
      else submit.focus();
    };
  }
  async function refreshHealth(mine) {
    try {
      const result = await get("/api/health");
      if (!active || mine !== generation) return;
      const collector = result?.collector;
      const counts = [];
      if (
        Number.isSafeInteger(result?.store?.events) &&
        result.store.events >= 0
      )
        counts.push(`전체 ${result.store.events}건`);
      for (const [key, label] of [
        ["written", "이번 실행 저장"],
        ["pending", "대기"],
        ["dropped", "누락"],
        ["duplicates", "중복"],
        ["conflicts", "충돌"],
      ])
        if (Number.isSafeInteger(collector?.[key]) && collector[key] >= 0)
          counts.push(`${label} ${collector[key]}`);
      health.textContent = counts.length
        ? counts.join(" · ")
        : "수집기 상태 확인 불가";
      if (typeof collector?.error === "string" && collector.error)
        health.textContent += ` · ${collector.error}`;
    } catch {
      if (active && mine === generation)
        health.textContent = "수집기 상태 조회 실패";
    }
  }
  async function load(append = false) {
    const nextDraft = append ? appliedDraft : draft();
    let path;
    try {
      path = eventQuery(nextDraft, append ? cursor : null);
    } catch (error) {
      queryError.textContent = error.message;
      return;
    }
    const mine = ++generation;
    ++detailGeneration;
    for (const controller of pending) controller.abort();
    queryError.textContent = "";
    submit.disabled = true;
    more.disabled = true;
    if (!append) {
      selected = null;
      inspector.hidden = true;
      events = [];
      cursor = null;
      message("원본 이벤트를 조회하는 중입니다.");
      count.textContent = "조회 중";
      more.hidden = true;
    }
    refreshHealth(mine);
    try {
      const page = validatePage(await get(path));
      if (!active || mine !== generation) return;
      const known = new Set(events.map((event) => event.event_id));
      events = [
        ...(append ? events : []),
        ...page.events.filter((event) => !known.has(event.event_id)),
      ];
      cursor = page.next_cursor;
      appliedDraft = { ...nextDraft };
      applied.textContent = `적용 조건 · ${nextDraft.source?.trim() || "전체 출처"} · ${nextDraft.trace_id?.trim() || "전체 흐름"} · ${nextDraft.since || "시작 제한 없음"} → ${nextDraft.until || "종료 제한 없음"} (KST)`;
      count.textContent = `현재 불러온 ${events.length}건`;
      more.hidden = cursor === null;
      renderRows();
    } catch (error) {
      if (!active || mine !== generation) return;
      queryError.textContent =
        error.message || "원본 이벤트를 조회하지 못했습니다.";
      if (!append) {
        message(
          "조회하지 못했습니다. 연결 상태를 확인하고 다시 조회하세요.",
          true,
        );
        count.textContent = "조회 실패";
      }
    } finally {
      if (active && mine === generation) {
        submit.disabled = false;
        more.disabled = false;
      }
    }
  }
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    load();
  });
  reset.addEventListener("click", () => {
    for (const [key, input] of Object.entries(controls))
      input.value = key === "limit" ? "50" : "";
    load();
  });
  more.addEventListener("click", () => {
    if (cursor !== null && !more.disabled) load(true);
  });
  return {
    activate() {
      if (active) return;
      active = true;
      load();
    },
    deactivate() {
      active = false;
      ++generation;
      ++detailGeneration;
      submit.disabled = false;
      more.disabled = false;
      for (const controller of pending) controller.abort();
    },
  };
}
