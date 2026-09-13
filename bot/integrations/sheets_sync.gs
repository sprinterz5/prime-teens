/**
 * PrimeTeens · синхронизация Google-таблицы с ботом.
 *
 * СХЕМА: БОТ САМ ЗАБИРАЕТ ДАННЫЕ, а не таблица их куда-то шлёт.
 *
 * Этот файл публикует таблицу как Web App (см. integrations/README.md —
 * там пошагово, как это сделать через Deploy → New deployment). После
 * публикации у тебя будет своя ссылка вида
 *   https://script.google.com/macros/s/XXXXX/exec
 * Бот дёргает эту ссылку сам — либо по расписанию (ночью, раз в сутки, из
 * его собственного планировщика), либо сразу по команде /sync_sheet.
 *
 * ПОЧЕМУ НЕ ТАК, КАК БЫЛО РАНЬШЕ (sendDocument боту через Bot API):
 * это оказалось нерабочей идеей. sendDocument от имени бота кладёт файл
 * В ЧАТ, но с точки зрения Telegram сообщение отправил САМ БОТ — а бот
 * получает через getUpdates только то, что ему прислали ЛЮДИ, а не эхо
 * своих же исходящих сообщений. Файл просто лежал в чате, и ничего не
 * происходило. Пришлось выяснять на живом запуске — сейчас так уже не будет.
 *
 * У пул-схемы забавный побочный эффект: BOT_TOKEN в этом файле больше не
 * нужен вообще — доступ к данным защищён отдельным секретом (SHEET_SECRET
 * ниже), который бот передаёт как ?token=... Значит, случайно показать
 * токен бота тому, у кого есть доступ на редактирование таблицы, теперь
 * невозможно — его тут просто нет.
 *
 * Формат структуры листа (блоки групп, шапка колонок, маркер) — см.
 * integrations/README.md рядом с этим файлом.
 */

// ==================== НАСТРОЙКИ — заполнить перед первым запуском ====================

// Секрет для доступа к Web App. Публикуемая ссылка технически открыта в
// интернете — без токена в запросе доГет отдаёт ошибку, а не данные.
// Сгенерируй любую случайную строку (например, https://www.uuidgenerator.net/)
// и впиши ТУ ЖЕ строку боту в .env как SHEETS_SYNC_TOKEN.
var SHEET_SECRET = 'ВСТАВЬ_СЮДА_СЛУЧАЙНУЮ_СТРОКУ';

// Название листа с реальными данными — ТОЧНО как написано на вкладке внизу
// таблицы. Не «активный лист» (что открыто у человека прямо сейчас) — так
// надёжнее: ночной автозабор бота не должен зависеть от того, какую вкладку
// кто-то последним кликнул в редакторе.
var SHEET_NAME = 'Группы';

// =======================================================================================


/**
 * Вызывается автоматически при открытии таблицы — добавляет меню
 * «PrimeTeens» с проверкой настроек (сама синхронизация теперь дело бота,
 * не таблицы — здесь просто самопроверка перед тем, как давать боту ссылку).
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('PrimeTeens')
    .addItem('Проверить настройки', 'checkConfig')
    .addItem('Показать ссылку для бота (после Deploy)', 'showWebAppUrl')
    .addToUi();
}


/**
 * Точка входа Web App. Бот дёргает её через GET с ?token=<SHEET_SECRET>.
 * ContentService не даёт ставить произвольный HTTP-статус — ошибки
 * возвращаются тем же 200, но с {ok: false, error: "..."} в теле; бот-сторона
 * обязана проверять поле ok, а не только код ответа.
 */
function doGet(e) {
  var token = (e && e.parameter) ? e.parameter.token : null;
  if (!SHEET_SECRET || String(SHEET_SECRET).indexOf('ВСТАВЬ') !== -1) {
    return jsonOutput_({ok: false, error: 'SHEET_SECRET не настроен в скрипте'});
  }
  if (token !== SHEET_SECRET) {
    return jsonOutput_({ok: false, error: 'неверный или отсутствующий token'});
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    return jsonOutput_({ok: false, error: 'лист «' + SHEET_NAME + '» не найден в таблице'});
  }

  return jsonOutput_({
    ok: true,
    source: 'google-sheets',
    spreadsheet: ss.getName(),
    sheet: sheet.getName(),
    exported_at: new Date().toISOString(),
    rows: readGridRows_(sheet)
  });
}

function jsonOutput_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}


/**
 * Проверка настроек без обращения к боту: секрет заполнен, нужный лист
 * существует и не пуст. Печатает понятный отчёт в alert.
 */
function checkConfig() {
  var ui = SpreadsheetApp.getUi();
  var problems = checkConfigProblems_();
  if (problems.length === 0) {
    ui.alert(
      'Настройки в порядке',
      'Секрет задан, лист «' + SHEET_NAME + '» найден и не пуст.\n\n' +
        'Если ещё не публиковал(а) Web App — Deploy → New deployment ' +
        '(инструкция в integrations/README.md), потом дай боту ссылку и токен.',
      ui.ButtonSet.OK
    );
  } else {
    ui.alert('Есть проблемы (' + problems.length + ')', problems.join('\n\n'), ui.ButtonSet.OK);
  }
}


/** Список проблем с настройками, пустой массив — всё в порядке. */
function checkConfigProblems_() {
  var problems = [];

  if (!SHEET_SECRET || String(SHEET_SECRET).indexOf('ВСТАВЬ') !== -1) {
    problems.push('Не заполнен SHEET_SECRET вверху скрипта (Extensions → Apps Script). ' +
      'Впиши случайную строку — она же должна быть у бота в .env как SHEETS_SYNC_TOKEN.');
  }

  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  if (!sheet) {
    problems.push('Лист «' + SHEET_NAME + '» не найден. Проверь название вкладки внизу ' +
      'таблицы или поправь SHEET_NAME в скрипте, если лист называется иначе.');
  } else if (sheet.getLastRow() === 0) {
    problems.push('Лист «' + SHEET_NAME + '» пустой — боту будет нечего забирать.');
  }

  return problems;
}


/**
 * Пробует показать текущий URL веб-приложения (работает только ПОСЛЕ хотя
 * бы одного Deploy → New deployment — до этого Apps Script ссылку ещё не
 * выдал, и функция честно об этом скажет).
 */
function showWebAppUrl() {
  var ui = SpreadsheetApp.getUi();
  var url;
  try {
    url = ScriptApp.getService().getUrl();
  } catch (e) {
    url = null;
  }
  if (url) {
    ui.alert('Ссылка для бота', url + '\n\nЭту ссылку и SHEET_SECRET дай боту в .env ' +
      '(SHEETS_SYNC_URL и SHEETS_SYNC_TOKEN).', ui.ButtonSet.OK);
  } else {
    ui.alert('Ссылки пока нет',
      'Веб-приложение ещё не опубликовано. Extensions → Apps Script → Deploy → ' +
        'New deployment → тип «Web app» → Execute as: Me, Who has access: Anyone. ' +
        'Подробности — integrations/README.md.',
      ui.ButtonSet.OK);
  }
}


// ---------------------------------------------------- сырая сетка листа

/**
 * Лист -> массив строк, строка -> массив значений ячеек. Весь разбор
 * (блоки групп, шапка колонок, маркер «Настоящие группы отсюда:») — на
 * стороне бота (app/roster_sheet.py), тут никакой интерпретации значений
 * нет — кроме одной вещи, критичной для дат (см. dateSafeValue_ ниже).
 */
function readGridRows_(sheet) {
  var values = sheet.getDataRange().getValues();
  var rows = [];
  for (var r = 0; r < values.length; r++) {
    var row = values[r];
    var out = [];
    for (var c = 0; c < row.length; c++) {
      out.push(dateSafeValue_(row[c]));
    }
    rows.push(out);
  }
  return rows;
}

/**
 * ЛОВУШКА ЧАСОВЫХ ПОЯСОВ. getDataRange().getValues() отдаёт значения дат
 * как JS-объекты Date. Если пропустить их в JSON.stringify как есть, дата
 * сериализуется в UTC-ISO (например, '2026-07-26T19:00:00.000Z') — а
 * таблица обычно в часовом поясе Asia/Almaty (+5), то есть 27.07.2026
 * 00:00 местного превращается в 26 июля по UTC. На стороне Python дата
 * молча съедет на день назад.
 *
 * Поэтому каждое значение типа Date форматируется здесь же, ДО
 * JSON.stringify, строкой 'yyyy-MM-dd' в часовом поясе САМОЙ ТАБЛИЦЫ
 * (getSpreadsheetTimeZone) — сериализуется уже обычная строка без времени
 * и без часового пояса, никакого пересчёта на стороне Python не требуется.
 */
function dateSafeValue_(v) {
  if (Object.prototype.toString.call(v) === '[object Date]') {
    var tz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
    return Utilities.formatDate(v, tz, 'yyyy-MM-dd');
  }
  return v;
}
