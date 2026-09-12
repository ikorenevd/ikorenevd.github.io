"use strict";

const clockFormat = new Intl.DateTimeFormat("en-GB", {hour: "2-digit", minute: "2-digit", hourCycle: "h23"});
const dayKey = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
const plusDays = (date, days) => { const result = new Date(date); result.setDate(result.getDate()+days); return result; };
state.calendarMode = "month";

// Every stored event is independent; all-day end dates are inclusive.
function calendarOccurrences(events, from, to) {
  const result = [];
  for (const event of events) {
    const start = new Date(event.all_day ? event.start+"T00:00:00" : event.start);
    const end = event.all_day ? plusDays(new Date(event.end+"T00:00:00"),1) : new Date(event.end);
    if (!Number.isFinite(+start) || !Number.isFinite(+end)) continue;
    const rule = event.recurrence;
    const weekly = rule?.frequency === "weekly";
    const step = 7 * (rule?.interval || 1);
    const durationDays = Math.ceil(Math.max(0, end-start)/86400000);
    let index = weekly ? Math.max(0, Math.floor((from-start-durationDays*86400000)/(step*86400000))-1) : 0;
    for (;; index++) {
      const occurrenceStart = plusDays(start, weekly ? index*step : 0);
      const occurrenceEnd = plusDays(end, weekly ? index*step : 0);
      if (occurrenceStart >= to || (weekly && rule.count && index >= rule.count)
        || (weekly && rule.until && dayKey(occurrenceStart) > rule.until)) break;
      if (occurrenceEnd > from || (+occurrenceEnd === +occurrenceStart && occurrenceStart >= from)) {
        result.push({...event, start: occurrenceStart, end: occurrenceEnd});
      }
      if (!weekly) break;
    }
  }
  return result.sort((a,b)=>a.start-b.start);
}

function calendarEntries(from, to) {
  const events=calendarOccurrences(state.events,from,to);
  for(const task of state.tasks) {
    const date=task.due_at||task.created_at;
    if(!date) continue;
    const moment=new Date(date);
    if(!task.due_at) moment.setHours(0,0,0,0);
    if(moment>=from && moment<to) events.push({start:moment,end:task.due_at?moment:plusDays(moment,1),all_day:!task.due_at,title:`${task.status==="done"?"✓":"Задача:"} ${task.title}${task.due_at?'':' · без срока'}`,taskId:task.id});
  }
  for(const media of state.media) {
    const milestones=[['added_at','Добавлено'],['completed_at',media.type==="book"?'Прочитано':'Просмотрено']];
    for(const [field,label] of milestones) {
      if(!media[field]) continue;
      const moment=new Date(media[field]);moment.setHours(0,0,0,0);
      if(moment>=from && moment<to) events.push({start:moment,end:plusDays(moment,1),all_day:true,title:`${typeName[media.type]} · ${label}: ${title(media)}`,mediaKey:`${media.type}:${media.sourceIndex}`});
    }
  }
  return events.sort((a,b)=>Number(!!b.all_day)-Number(!!a.all_day)||a.start-b.start);
}

function entryButton(event,date,next) {
  const target=event.taskId?`data-task="${esc(event.taskId)}"`:event.mediaKey?`data-media="${esc(event.mediaKey)}"`:`data-event="${esc(event.id)}"`;
  const label=event.all_day?"Весь день":event.taskId?clockFormat.format(event.start):`${event.start<date?"00:00":clockFormat.format(event.start)}–${event.end>=next?"24:00":clockFormat.format(event.end)}`;
  return `<button class="event ${event.mediaKey?'media-event':event.taskId?'task-event':event.all_day?'all-day-event':''}" ${target}><time>${label}</time> ${esc(event.title)}</button>`;
}

const controls = document.createElement("div");
controls.className = "filters calendar-modes";
controls.innerHTML = '<button data-mode="day">День</button><button data-mode="week">Неделя</button><button data-mode="month" class="active">Месяц</button>';
$("calendar-grid").previousElementSibling.before(controls);
controls.addEventListener("click", e => {
  if (!e.target.dataset.mode) return;
  state.calendarMode=e.target.dataset.mode; renderCalendar();
});

renderCalendar = function () {
  const mode=state.calendarMode, anchor=new Date(state.month);
  anchor.setHours(0,0,0,0);
  const from=mode==="month" ? new Date(anchor.getFullYear(),anchor.getMonth(),1)
    : mode==="week" ? plusDays(anchor,-((anchor.getDay()+6)%7)) : anchor;
  const to=mode==="month" ? new Date(from.getFullYear(),from.getMonth()+1,1) : plusDays(from,mode==="week"?7:1);
  const events=calendarEntries(from,to);
  controls.querySelectorAll("button").forEach(b=>b.classList.toggle("active",b.dataset.mode===mode));
  $("month-title").textContent=mode==="month" ? new Intl.DateTimeFormat("ru-RU",{month:"long",year:"numeric"}).format(from)
    : mode==="day" ? df.format(from) : `${df.format(from)} — ${df.format(plusDays(to,-1))}`;
  const grid=$("calendar-grid");
  document.querySelector(".weekdays").hidden=mode!=="month";
  grid.className=mode==="month"?"calendar-grid":"agenda-grid";
  let html=mode==="month"?'<div class="day muted"></div>'.repeat((from.getDay()+6)%7):"";
  for(let date=new Date(from);date<to;date=plusDays(date,1)) {
    const next=plusDays(date,1);
    const items=events.filter(e=>e.start<next && (e.end>date || (+e.start===+e.end && e.start>=date)));
    const heading=mode==="month"?date.getDate():`${new Intl.DateTimeFormat("ru-RU",{weekday:"long"}).format(date)}, ${df.format(date)}`;
    html+=`<div class="${mode==="month"?"day":"agenda-day"} ${dayKey(date)===dayKey(new Date())?"today":""}" data-day="${dayKey(date)}"><b>${heading}</b>${items.map(e=>entryButton(e,date,next)).join("")}${mode!=="month"&&!items.length?'<p class="free-day">Нет событий</p>':""}</div>`;
  }
  grid.innerHTML=html;
};
function moveCalendar(direction) {
  state.month=state.calendarMode==="month" ? new Date(state.month.getFullYear(),state.month.getMonth()+direction,1)
    : plusDays(state.month,direction*(state.calendarMode==="week"?7:1));
  renderCalendar();
}
$("prev-month").onclick=()=>moveCalendar(-1);
$("next-month").onclick=()=>moveCalendar(1);
$("prev-month").setAttribute("aria-label","Предыдущий период");
$("next-month").setAttribute("aria-label","Следующий период");

const basicEditor=openEditor;
openEditor=function(kind,item=null,day=null) {
  if(!canEdit) return;
  basicEditor(kind,item,day);
  // Text inputs ensure the same date/time format on every OS and browser.
  $("editor-fields").querySelectorAll('input[type="datetime-local"]').forEach(input=>{
    const value=input.value;
    input.type="text"; input.placeholder="дд/мм/гггг чч:мм";
    input.value=value?`${df.format(new Date(value))} ${clockFormat.format(new Date(value))}`:"";
    input.dataset.moment="true";
  });
  if(kind!=="event") return;
  $("editor-fields").insertAdjacentHTML("afterbegin",'<label class="all-day-choice"><input type="checkbox" name="all_day"> Весь день</label>');
  const form=$("editor-form");
  form.elements.all_day.checked=!!item?.all_day;
  const syncAllDay=()=>{
    const allDay=form.elements.all_day.checked;
    for(const name of ['start','end']) {
      const input=form.elements[name];
      input.placeholder=allDay?'дд/мм/гггг':'дд/мм/гггг чч:мм';
      input.value=allDay?input.value.slice(0,10):input.value.length===10?input.value+' '+(name==='start'?'09:00':'10:00'):input.value;
    }
  };
  if(item?.all_day) {
    form.elements.start.value=item.start.split('-').reverse().join('/');
    form.elements.end.value=item.end.split('-').reverse().join('/');
  }
  form.elements.all_day.onchange=syncAllDay;syncAllDay();
  if(item) {
    $("editor-fields").insertAdjacentHTML('beforeend','<small>Изменение и удаление касается только этого события.</small>');
    return;
  }
  const rule=item?.recurrence;
  $("editor-fields").insertAdjacentHTML("beforeend",`<label>Повторение<select name="repeat"><option value="none">Не повторяется</option><option value="weekly">Еженедельно</option></select></label><div id="repeat-fields"><label>Каждые … недель<input name="interval" type="number" min="1" max="520" value="${rule?.interval||1}"></label><label>Окончание повторов<select name="repeat_end"><option value="until">До даты включительно</option><option value="count">После указанного числа событий</option></select></label><label id="until-label">Последняя дата<input name="until" placeholder="дд/мм/гггг" value="${rule?.until?esc(rule.until.split("-").reverse().join("/")):""}"></label><label id="count-label">Всего событий (включая первое)<input name="count" type="number" min="1" max="10000" value="${rule?.count||10}"></label><small>Каждый повтор сохраняется отдельным событием и редактируется независимо.</small></div>`);
  form.elements.repeat.value=rule?"weekly":"none";
  form.elements.repeat_end.value=rule?.count?"count":"until";
  const sync=()=>{
    $("repeat-fields").hidden=form.elements.repeat.value==="none";
    $("until-label").hidden=form.elements.repeat_end.value!=="until";
    $("count-label").hidden=form.elements.repeat_end.value!=="count";
  };
  form.elements.repeat.onchange=form.elements.repeat_end.onchange=sync;sync();
};

function parseEuropean(value, withTime=true) {
  const match=value.trim().match(withTime?/^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})$/:/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if(!match) throw Error(withTime?"Введите дату и время: дд/мм/гггг чч:мм":"Введите дату: дд/мм/гггг");
  const [,d,m,y,h="00",minute="00"]=match;
  const date=new Date(`${y}-${m}-${d}T${h}:${minute}:00`);
  if(!Number.isFinite(+date)||date.getDate()!==+d||date.getMonth()+1!==+m||date.getFullYear()!==+y||date.getHours()!==+h||date.getMinutes()!==+minute) throw Error("Некорректная дата или время");
  return date;
}
const basicSave=save;
$("editor-form").onsubmit=async function(e) {
  e.preventDefault();
  if(!canEdit) return;
  const form=e.currentTarget;
  try {
    const inputs=[...form.querySelectorAll("[data-moment]")];
    const allDay=!!form.elements.all_day?.checked;
    const parsed=inputs.map(input=>input.value.trim()?parseEuropean(input.value,!allDay):null);
    if(state.edit.kind!=="event") {
      const original=inputs.map(input=>input.value);
      inputs.forEach((input,i)=>input.value=parsed[i]?parsed[i].toISOString():"");
      await basicSave(e);
      inputs.forEach((input,i)=>input.value=original[i]);
      return;
    }
    const data=Object.fromEntries(new FormData(form)),item=state.edit.item;
    const start=parsed[0],end=parsed[1];
    if(!start||!end||end<start) throw Error("Укажите начало и окончание; окончание не должно быть раньше начала");
    if(!data.title.trim()) throw Error("Введите название события");
    let recurrence=null;
    if(data.repeat==="weekly") {
      const interval=Number(data.interval);
      if(!Number.isInteger(interval)||interval<1||interval>520) throw Error("Интервал: от 1 до 520 недель");
      recurrence={frequency:"weekly",interval};
      if(data.repeat_end==="count") {
        const count=Number(data.count);
        if(!Number.isInteger(count)||count<1||count>10000) throw Error("Количество: от 1 до 10000 событий");
        recurrence.count=count;
      } else {
        recurrence.until=dayKey(parseEuropean(data.until,false));
        if(recurrence.until<dayKey(start)) throw Error("Последняя дата не должна быть раньше первого события");
      }
    }
    await api(`events${item?`/${item.id}`:""}`,{method:item?"PUT":"POST",body:JSON.stringify({...item,title:data.title.trim(),start:allDay?dayKey(start):start.toISOString(),end:allDay?dayKey(end):end.toISOString(),all_day:allDay,notes:data.notes.trim(),recurrence})});
    $("editor").close();await load();toast("Сохранено");
  } catch(error) { $("form-error").textContent=error.message; }
};
renderCalendar();
