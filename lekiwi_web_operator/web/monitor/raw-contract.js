/** Read-only event contract. No risk classification or robot control belongs here. */
const text = (value, max = 512) =>
  typeof value === "string" && value.length > 0 && value.length <= max;
function validSequence(value) {
  return (
    (Number.isSafeInteger(value) && value >= 0) ||
    (typeof value === "string" &&
      /^(0|[1-9]\d{0,18})$/.test(value) &&
      BigInt(value) <= 9223372036854775807n)
  );
}
export function validTimestamp(value) {
  return (
    typeof value === "string" &&
    /(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}
export function validateEvent(value) {
  if (
    !value ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    value.schema_version !== 1 ||
    !text(value.event_id) ||
    !text(value.source) ||
    !text(value.run_id) ||
    !validSequence(value.sequence) ||
    !validTimestamp(value.occurred_at) ||
    !validTimestamp(value.observed_at) ||
    !text(value.stage) ||
    !text(value.outcome) ||
    !value.payload ||
    typeof value.payload !== "object" ||
    Array.isArray(value.payload) ||
    (value.record_id !== undefined &&
      (!Number.isSafeInteger(value.record_id) || value.record_id < 1)) ||
    ["trace_id", "command_id", "reason_code"].some(
      (key) => value[key] != null && !text(value[key]),
    ) ||
    (value.raw_json !== undefined && typeof value.raw_json !== "string")
  )
    throw Error("원본 이벤트 응답 형식을 확인하지 못했습니다.");
  return value;
}
export function validatePage(value) {
  if (
    !value ||
    !Array.isArray(value.events) ||
    value.events.length > 100 ||
    !(
      value.next_cursor === null ||
      (Number.isSafeInteger(value.next_cursor) && value.next_cursor > 0)
    )
  )
    throw Error("원본 목록 응답 형식을 확인하지 못했습니다.");
  value.events.forEach(validateEvent);
  if (
    new Set(value.events.map((event) => event.event_id)).size !==
    value.events.length
  )
    throw Error("원본 목록에 중복 식별자가 있습니다.");
  return value;
}
function kstTimestamp(value) {
  if (!value) return "";
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(value))
    throw Error("조회 시각을 확인하세요.");
  const parsed = new Date(value + "+09:00");
  if (
    !Number.isFinite(parsed.getTime()) ||
    new Date(parsed.getTime() + 9 * 3600000)
      .toISOString()
      .slice(0, value.length) !== value
  )
    throw Error("조회 시각을 확인하세요.");
  return parsed.toISOString();
}
export function eventQuery(draft, cursor = null) {
  const limit = Number(draft.limit);
  if (
    !/^\d+$/.test(String(draft.limit)) ||
    !Number.isSafeInteger(limit) ||
    limit < 1 ||
    limit > 100
  )
    throw Error("조회 개수는 1~100 사이로 입력하세요.");
  const since = kstTimestamp(draft.since);
  const until = kstTimestamp(draft.until);
  if (since && until && since >= until)
    throw Error("종료 시각을 시작 시각보다 늦게 지정하세요.");
  const query = new URLSearchParams({ limit: String(limit) });
  for (const [key, value] of Object.entries({
    source: draft.source?.trim(),
    trace_id: draft.trace_id?.trim(),
    since,
    until,
  })) {
    if (!value) continue;
    if (value.length > 256) throw Error("조회 조건은 256자 이내로 입력하세요.");
    query.set(key, value);
  }
  if (cursor !== null) {
    if (!Number.isSafeInteger(cursor) || cursor < 1)
      throw Error("목록 커서가 올바르지 않습니다.");
    query.set("after", String(cursor));
  }
  return "/api/events?" + query.toString();
}
export function eventPath(id) {
  if (!text(id)) throw Error("이벤트 식별자가 올바르지 않습니다.");
  return "/api/events/" + encodeURIComponent(id);
}
export function displayTime(value) {
  return validTimestamp(value)
    ? new Date(Date.parse(value) + 9 * 3600000)
        .toISOString()
        .replace("T", " ")
        .replace(/\.\d{3}Z$/, " KST")
    : "시각 확인 불가";
}
