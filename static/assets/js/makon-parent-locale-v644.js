/* MakonBook V64.4 — Parent Portal locale parity with landing.
 * Client-side EN/RU/UZ changes without navigation or data fetching.
 * Server-rendered data and access checks are never modified.
 */
(function () {
  'use strict';
  if (!document.body || !document.body.classList.contains('mb642-parent-page')) return;
  const KEY = 'makonbook.public.language.v62';
  const dictionary = {"en":{"page_title":"Parent Portal | SAT Makon","open_menu":"Open menu","main_navigation":"Main navigation","home":"Home","student_rating":"Student Rating","parent_access":"Parent access","leaderboard":"Leaderboard","landing_page":"Landing page","back_to_makonbook":"Back to MakonBook","parent_title":"Parent access","parent_intro":"Enter the phone number registered on the student's SATMakon account. After a successful lookup, this browser keeps the student open after refresh so you do not have to enter the phone number every time.","public_leaderboard":"Public leaderboard","student_access_code":"Registered phone number","code_placeholder":"+998 90 123 45 67","open_rating":"Open student stats","rank":"Rank","rating":"Rating","assessments":"Assessments","classrooms":"Classrooms","date":"Date","classroom":"Classroom","homework":"Homework","progress":"Progress","activity":"Activity","attendance":"Attendance","behavior":"Behavior","mean":"Mean","no_history":"No rating history is available yet.","footer_text":"Digital SAT practice platform with tests, analytics, classrooms, and student rating.","back_to_top":"Back to top","language":"Language","report_issue":"Report issue","report_problem":"Report a problem","close":"Close","report_description":"Describe what happened and what you expected. This is one general platform report, not an automatic request to change an answer key.","category":"Category","technical_problem":"Technical problem","content_problem":"Question or content problem","account_problem":"Account or access problem","rating_problem":"Rating problem","suggestion":"Suggestion","other":"Other","name_optional":"Name (optional)","email_optional":"Email (optional)","comment":"Comment","comment_placeholder":"Example: I could not open my child's statistics using the registered phone number...","send_report":"Send report","sending":"Sending...","report_sent":"Report sent. Thank you.","report_failed":"Could not send report.","too_many_attempts":"Too many phone-number lookup attempts. Try again later.","code_not_found":"Phone number not found. Enter the phone number registered on the student's SATMakon account.","remembered_on_device":"Remembered on this device","switch_student":"Use another student","registration_help":"Use the phone number already registered on the student's SATMakon account. No separate parent code is required.","device_note":"After the first successful lookup, this browser remembers the student. Refreshing the page will keep the statistics open. Use “Use another student” on shared devices when you are finished.","use_registered_phone":"Use the student's registered phone number","support":"Support","multiple_students_title":"Choose a student","multiple_students_intro":"This phone number is linked to more than one student. Select the student whose statistics you want to open.","select_student":"Open statistics","use_another_phone":"Use another phone number","records":"records","family_view":"SAT Makon · Family view","verified_family":"VERIFIED FAMILY ACCESS","academic_progress":"Academic progress","academic_intro":"Official term grades, every SAT practice attempt and synced attendance.","verified":"Verified","grades":"Mid-term / Final-term grades","no_grades":"No term grades entered yet. These grades are supplied by staff, never estimated from SAT scores.","practice":"All practice results","col_test":"Test","col_attempt":"Attempt","col_score":"Score","archived_test":"Archived test","no_practice":"No finished practice attempts yet.","previous":"Previous","next":"Next","page":"Page","vocabulary":"Vocabulary practice","col_activity":"Activity","col_date":"Date","independent":"Independent practice","no_vocabulary":"No vocabulary practice results yet.","ap_exams":"AP practice exams","col_exam":"Exam","col_submitted":"Submitted","attempt_prefix":"Attempt #","no_ap":"No submitted AP exam attempts yet.","hollihop":"Hollihop attendance","present":"Present","absent":"Absent","attendance_rate":"Attendance rate","col_status":"Status","attendance_note":"Latest 60 attendance records. Totals cover all synchronized records.","private_report":"PRIVATE FAMILY REPORT","unlock_progress":"Unlock detailed progress","private_intro":"Mid-term and final-term grades, practice attempts and Hollihop attendance require the family code shared by the student. A phone number alone is not enough to reveal academic records.","family_code":"Family access code","family_placeholder":"Enter your family code","unlock_report":"Unlock report","col_classroom":"Classroom","mock_exams":"Mock exams","login":"Login","progress_label":"Progress","private_attempts":"Too many private access attempts. Try again later.","invalid_private":"Invalid family access code.","choose_site_lang":"Choose site language","site_lang":"Site language","no_attendance":"No synced Hollihop attendance yet.","term_midterm":"Mid-term","term_final":"Final-term"},"ru":{"page_title":"Родительский портал | SAT Makon","open_menu":"Открыть меню","main_navigation":"Главная навигация","home":"Главная","student_rating":"Рейтинг учеников","parent_access":"Для родителей","leaderboard":"Рейтинг","landing_page":"Главная страница","back_to_makonbook":"Вернуться в MakonBook","parent_title":"Доступ для родителей","parent_intro":"Введите номер телефона, зарегистрированный в аккаунте ученика SATMakon. После успешного поиска браузер запомнит ученика, поэтому после обновления вводить номер повторно не нужно.","public_leaderboard":"Общий рейтинг","student_access_code":"Зарегистрированный номер телефона","code_placeholder":"+998 90 123 45 67","open_rating":"Открыть статистику","rank":"Место","rating":"Рейтинг","assessments":"Оценивания","classrooms":"Классы","date":"Дата","classroom":"Класс","homework":"Домашняя работа","progress":"Прогресс","activity":"Активность","attendance":"Посещаемость","behavior":"Поведение","mean":"Среднее","no_history":"Истории оценивания пока нет.","footer_text":"Платформа подготовки к Digital SAT: тесты, аналитика, классы и рейтинг учеников.","back_to_top":"Наверх","language":"Язык","report_issue":"Сообщить о проблеме","report_problem":"Сообщить о проблеме","close":"Закрыть","report_description":"Опишите, что произошло и какой результат вы ожидали. Это общее сообщение о проблеме платформы.","category":"Категория","technical_problem":"Техническая проблема","content_problem":"Проблема с вопросом или содержанием","account_problem":"Проблема с аккаунтом или доступом","rating_problem":"Проблема с рейтингом","suggestion":"Предложение","other":"Другое","name_optional":"Имя (необязательно)","email_optional":"Email (необязательно)","comment":"Комментарий","comment_placeholder":"Например: я не смог открыть статистику ребёнка по зарегистрированному номеру телефона...","send_report":"Отправить","sending":"Отправка...","report_sent":"Сообщение отправлено. Спасибо.","report_failed":"Не удалось отправить сообщение.","too_many_attempts":"Слишком много попыток поиска по номеру телефона. Попробуйте позже.","code_not_found":"Номер телефона не найден. Введите номер, зарегистрированный в аккаунте ученика SATMakon.","remembered_on_device":"Сохранено на этом устройстве","switch_student":"Другой ученик","registration_help":"Введите номер телефона, который уже зарегистрирован в аккаунте ученика SATMakon. Отдельный код для родителей не нужен.","device_note":"После первого успешного поиска этот браузер запомнит ученика. После обновления страницы статистика останется открытой. На общем устройстве используйте кнопку «Другой ученик», когда закончите.","use_registered_phone":"Используйте номер телефона, зарегистрированный у ученика","support":"Поддержка","multiple_students_title":"Выберите ученика","multiple_students_intro":"Этот номер телефона привязан к нескольким ученикам. Выберите, чью статистику нужно открыть.","select_student":"Открыть статистику","use_another_phone":"Использовать другой номер","records":"записей","family_view":"SAT Makon · Семейный кабинет","verified_family":"ПОДТВЕРЖДЁННЫЙ СЕМЕЙНЫЙ ДОСТУП","academic_progress":"Успеваемость ученика","academic_intro":"Оценки за четверть, все попытки SAT и синхронизированная посещаемость.","verified":"Подтверждено","grades":"Оценки Mid-term / Final-term","no_grades":"Пока нет итоговых оценок. Их вносят сотрудники, а не рассчитывают на основе SAT.","practice":"Все результаты практики","col_test":"Тест","col_attempt":"Попытка","col_score":"Балл","archived_test":"Архивный тест","no_practice":"Завершённых попыток пока нет.","previous":"Назад","next":"Далее","page":"Страница","vocabulary":"Словарная практика","col_activity":"Активность","col_date":"Дата","independent":"Самостоятельная практика","no_vocabulary":"Результатов по словарю пока нет.","ap_exams":"Пробные экзамены AP","col_exam":"Экзамен","col_submitted":"Отправлено","attempt_prefix":"Попытка №","no_ap":"Отправленных работ AP пока нет.","hollihop":"Посещаемость Hollihop","present":"Присутствовал","absent":"Отсутствовал","attendance_rate":"Процент посещаемости","col_status":"Статус","attendance_note":"Последние 60 записей. Итоги рассчитаны по всем синхронизированным данным.","private_report":"КОНФИДЕНЦИАЛЬНЫЙ ОТЧЁТ","unlock_progress":"Открыть подробные результаты","private_intro":"Для просмотра оценок, попыток и посещаемости нужен семейный код ученика. Одного номера телефона недостаточно.","family_code":"Семейный код доступа","family_placeholder":"Введите семейный код","unlock_report":"Открыть отчёт","col_classroom":"Класс","mock_exams":"Пробные экзамены","login":"Войти","progress_label":"Прогресс","private_attempts":"Слишком много попыток ввода семейного кода. Попробуйте позже.","invalid_private":"Неверный семейный код.","choose_site_lang":"Выбрать язык сайта","site_lang":"Язык сайта","no_attendance":"Данные посещаемости из Hollihop пока не синхронизированы.","term_midterm":"Промежуточная","term_final":"Итоговая"},"uz":{"page_title":"Ota-onalar portali | SAT Makon","open_menu":"Menyuni ochish","main_navigation":"Asosiy navigatsiya","home":"Bosh sahifa","student_rating":"O‘quvchilar reytingi","parent_access":"Ota-onalar uchun","leaderboard":"Reyting","landing_page":"Bosh sahifa","back_to_makonbook":"MakonBook’ga qaytish","parent_title":"Ota-onalar uchun kirish","parent_intro":"O‘quvchining SATMakon akkauntida ro‘yxatdan o‘tgan telefon raqamini kiriting. Muvaffaqiyatli qidiruvdan so‘ng brauzer o‘quvchini eslab qoladi.","public_leaderboard":"Umumiy reyting","student_access_code":"Ro‘yxatdan o‘tgan telefon raqami","code_placeholder":"+998 90 123 45 67","open_rating":"Statistikani ochish","rank":"O‘rin","rating":"Reyting","assessments":"Baholashlar","classrooms":"Sinflar","date":"Sana","classroom":"Sinf","homework":"Uy vazifasi","progress":"O‘sish","activity":"Faollik","attendance":"Davomat","behavior":"Xulq-atvor","mean":"O‘rtacha","no_history":"Hozircha baholash tarixi mavjud emas.","footer_text":"Digital SAT tayyorgarlik platformasi: testlar, tahlil, sinflar va o‘quvchilar reytingi.","back_to_top":"Yuqoriga","language":"Til","report_issue":"Muammo haqida xabar berish","report_problem":"Muammo haqida xabar berish","close":"Yopish","report_description":"Nima sodir bo‘lganini va qanday natija kutganingizni yozing. Bu platformadagi umumiy muammo haqida xabar.","category":"Toifa","technical_problem":"Texnik muammo","content_problem":"Savol yoki kontent bilan bog‘liq muammo","account_problem":"Hisob yoki kirish bilan bog‘liq muammo","rating_problem":"Reyting bilan bog‘liq muammo","suggestion":"Taklif","other":"Boshqa","name_optional":"Ism (ixtiyoriy)","email_optional":"Email (ixtiyoriy)","comment":"Izoh","comment_placeholder":"Masalan: ro‘yxatdan o‘tgan telefon raqami orqali farzandimning statistikasini ocha olmadim...","send_report":"Yuborish","sending":"Yuborilmoqda...","report_sent":"Xabar yuborildi. Rahmat.","report_failed":"Xabarni yuborib bo‘lmadi.","too_many_attempts":"Telefon raqami orqali qidirish urinishlari juda ko‘p. Keyinroq qayta urinib ko‘ring.","code_not_found":"Telefon raqami topilmadi. O‘quvchining SATMakon akkauntida ro‘yxatdan o‘tgan raqamni kiriting.","remembered_on_device":"Ushbu qurilmada saqlandi","switch_student":"Boshqa o‘quvchi","registration_help":"O‘quvchining SATMakon akkauntida allaqachon ro‘yxatdan o‘tgan telefon raqamidan foydalaning. Alohida ota-ona kodi kerak emas.","device_note":"Birinchi muvaffaqiyatli qidiruvdan so‘ng ushbu brauzer o‘quvchini eslab qoladi. Sahifa yangilanganda statistika ochiq qoladi. Umumiy qurilmada ish tugagach «Boshqa o‘quvchi» tugmasidan foydalaning.","use_registered_phone":"O‘quvchining ro‘yxatdan o‘tgan telefon raqamidan foydalaning","support":"Yordam","multiple_students_title":"O‘quvchini tanlang","multiple_students_intro":"Bu telefon raqami bir nechta o‘quvchiga biriktirilgan. Statistikasi ochilishi kerak bo‘lgan o‘quvchini tanlang.","select_student":"Statistikani ochish","use_another_phone":"Boshqa telefon raqamidan foydalanish","records":"yozuv","family_view":"SAT Makon · Oila kabineti","verified_family":"TASDIQLANGAN OILAVIY KIRISH","academic_progress":"O‘quvchi natijalari","academic_intro":"Oraliq va yakuniy baholar, barcha SAT urinishlari va sinxronlangan davomat.","verified":"Tasdiqlangan","grades":"Mid-term / Final-term baholari","no_grades":"Hozircha davriy baholar kiritilmagan. Baholar SAT natijasidan hisoblanmaydi, xodimlar tomonidan kiritiladi.","practice":"Barcha mashq natijalari","col_test":"Test","col_attempt":"Urinish","col_score":"Ball","archived_test":"Arxiv testi","no_practice":"Hozircha yakunlangan mashqlar yo‘q.","previous":"Oldingi","next":"Keyingi","page":"Sahifa","vocabulary":"Lug‘at mashqlari","col_activity":"Faoliyat","col_date":"Sana","independent":"Mustaqil mashq","no_vocabulary":"Hozircha lug‘at mashqlari natijalari yo‘q.","ap_exams":"AP sinov imtihonlari","col_exam":"Imtihon","col_submitted":"Yuborilgan","attempt_prefix":"Urinish №","no_ap":"Hozircha yuborilgan AP imtihon natijalari yo‘q.","hollihop":"Hollihop davomati","present":"Qatnashgan","absent":"Qatnashmagan","attendance_rate":"Davomat foizi","col_status":"Holat","attendance_note":"Oxirgi 60 ta davomat yozuvi. Umumiy natijalar barcha sinxronlangan yozuvlarni qamrab oladi.","private_report":"MAXFIY OILAVIY HISOBOT","unlock_progress":"Batafsil natijalarni ochish","private_intro":"Baholar, urinishlar va davomatni ko‘rish uchun o‘quvchi bergan oilaviy kod kerak. Faqat telefon raqami yetarli emas.","family_code":"Oilaviy kirish kodi","family_placeholder":"Oilaviy kodingizni kiriting","unlock_report":"Hisobotni ochish","col_classroom":"Sinf","mock_exams":"Sinov imtihonlari","login":"Kirish","progress_label":"O‘sish","private_attempts":"Oilaviy kodni kiritish urinishlari juda ko‘p. Keyinroq urinib ko‘ring.","invalid_private":"Oilaviy kirish kodi noto‘g‘ri.","choose_site_lang":"Sayt tilini tanlash","site_lang":"Sayt tili","no_attendance":"Hollihop davomati hali sinxronlanmagan.","term_midterm":"Oraliq","term_final":"Yakuniy"}};
  const valid = ['en', 'ru', 'uz'];
  const root = document.querySelector('[data-mb642-parent-locale]');
  const trigger = root && root.querySelector('[data-mb63-lang-trigger]');
  const currentLabel = root && root.querySelector('[data-mb63-lang-current]');
  const choices = root && Array.from(root.querySelectorAll('[data-mb63-lang-option]'));
  if (!root || !trigger || !currentLabel || !choices || !choices.length) return;
  const navKeys = ['Platform', 'Results', 'Parents', 'FAQ'];
  const navI18n = {
    en: ['Platform', 'Results', 'Parents', 'FAQ', 'Mock exams', 'Log in'],
    ru: ['Платформа', 'Результаты', 'Родителям', 'Вопросы и ответы', 'Пробные экзамены', 'Войти'],
    uz: ['Platforma', 'Natijalar', 'Ota-onalarga', 'Savol-javob', 'Sinov imtihonlari', 'Kirish']
  };
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
  const params = new URL(window.location.href).searchParams;
  let stored = null;
  try { stored = window.localStorage.getItem(KEY); } catch (_) { /* storage disabled */ }
  const htmlLang = (document.documentElement.lang || 'en').toLowerCase().split('-')[0];
  const queryLang = params.get('lang');
  let lang = valid.includes(queryLang) ? queryLang : valid.includes(stored) ? stored : valid.includes(htmlLang) ? htmlLang : 'en';
  let busy = false;

  function writeLanguage() {
    // The server reads POST lang to choose the correct localized response.
    document.querySelectorAll('form').forEach(form => {
      if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post') return;
      let input = form.querySelector('input[name="lang"]');
      if (!input) {
        input = document.createElement('input');
        input.type = 'hidden'; input.name = 'lang'; form.appendChild(input);
      }
      input.value = lang;
    });
    // Pagination and any other page-specific lang URLs retain all query parameters.
    document.querySelectorAll('a[href*="lang="]').forEach(link => {
      if (link.closest('.mb56-nav-wrap')) return;
      try {
        const url = new URL(link.getAttribute('href'), window.location.href);
        if (url.origin !== window.location.origin) return;
        url.searchParams.set('lang', lang);
        link.setAttribute('href', url.pathname + url.search + url.hash);
      } catch (_) { /* invalid URL: don't mutate */ }
    });
    try {
      const url = new URL(window.location.href);
      if (url.searchParams.get('lang') !== lang) {
        url.searchParams.set('lang', lang);
        window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
      }
    } catch (_) { /* history not accessible */ }
  }

  function translateMessages() {
    // Only known server error messages. Never rewrite user names, scores, or comments.
    const messageText = {
      'Too many private access attempts. Try again later.': 'private_attempts',
      'Invalid family access code.': 'invalid_private'
    };
    document.querySelectorAll('.mkp-parent-message, .mb60-parent-message').forEach(element => {
      const text = element.textContent.trim();
      if (!element.dataset.mb644Message) {
        if (messageText[text]) element.dataset.mb644Message = messageText[text];
        else {
          for (const name of ['code_not_found', 'too_many_attempts', 'private_attempts', 'invalid_private']) {
            if (valid.some(locale => dictionary[locale][name] === text)) {
              element.dataset.mb644Message = name;
              break;
            }
          }
        }
      }
      const key = element.dataset.mb644Message;
      if (key && dictionary[lang][key]) element.textContent = dictionary[lang][key];
    });
  }

  function translate() {
    document.documentElement.lang = lang;
    currentLabel.textContent = lang.toUpperCase();
    choices.forEach(choice => {
      const selected = choice.dataset.mb63LangOption === lang;
      choice.setAttribute('aria-selected', String(selected));
      choice.tabIndex = selected ? 0 : -1;
    });
    const t = dictionary[lang];
    document.querySelectorAll('[data-mb644-key]').forEach(element => {
      const value = t[element.dataset.mb644Key];
      if (typeof value === 'string') element.textContent = value;
    });
    document.querySelectorAll('[data-mb644-placeholder]').forEach(element => {
      const value = t[element.dataset.mb644Placeholder];
      if (typeof value === 'string') element.setAttribute('placeholder', value);
    });
    document.querySelectorAll('[data-mb644-term]').forEach(element => {
      const key = 'term_' + element.dataset.mb644Term;
      if (t[key]) element.textContent = t[key];
    });
    document.querySelectorAll('[data-mb644-attendance-status]').forEach(element => {
      const key = element.dataset.mb644AttendanceStatus;
      if (t[key]) element.textContent = t[key];
    });
    const links = document.querySelectorAll('.mb56-nav-wrap .mb56-nav-links a');
    links.forEach((element, index) => {
      if (index < navKeys.length) element.textContent = navI18n[lang][index];
    });
    const mock = document.querySelector('.mb56-nav-wrap .mb56-btn-quiet');
    if (mock) mock.textContent = navI18n[lang][4];
    const login = document.querySelector('.mb56-nav-wrap .mb56-btn-login');
    if (login) {
      const textNode = Array.from(login.childNodes).find(node => node.nodeType === Node.TEXT_NODE);
      if (textNode) textNode.nodeValue = navI18n[lang][5] + ' ';
      else login.prepend(document.createTextNode(navI18n[lang][5] + ' '));
    }
    document.title = t.page_title;
    trigger.setAttribute('aria-label', t.choose_site_lang);
    const menu = root.querySelector('[role="listbox"]');
    if (menu) menu.setAttribute('aria-label', t.site_lang);
    translateMessages();
    writeLanguage();
    try { window.localStorage.setItem(KEY, lang); } catch (_) { /* unavailable */ }
  }

  function closeMenu(restoreFocus) {
    root.classList.remove('is-open');
    trigger.setAttribute('aria-expanded', 'false');
    if (restoreFocus) trigger.focus({preventScroll:true});
  }
  function openMenu() {
    const open = !root.classList.contains('is-open');
    root.classList.toggle('is-open', open);
    trigger.setAttribute('aria-expanded', String(open));
    if (open) {
      const selected = choices.find(choice => choice.dataset.mb63LangOption === lang);
      if (selected) selected.focus({preventScroll:true});
    }
  }

  trigger.addEventListener('click', event => { event.stopPropagation(); openMenu(); });
  choices.forEach(choice => {
    choice.addEventListener('click', async () => {
      const next = choice.dataset.mb63LangOption;
      closeMenu(true);
      if (!valid.includes(next) || next === lang || busy) return;
      busy = true;
      const commit = () => { lang = next; translate(); };
      try {
        const animator = window.MakonBookLandingTransition;
        if (animator && !(reduce && reduce.matches)) await animator.run(commit);
        else commit();
      } catch (error) {
        console.warn('[MakonBook] Parent language transition failed:', error);
        if (lang !== next) commit();
      } finally {
        busy = false;
      }
    });
    choice.addEventListener('keydown', event => {
      const index = choices.indexOf(choice);
      let target = null;
      if (event.key === 'ArrowDown') target = choices[(index + 1) % choices.length];
      else if (event.key === 'ArrowUp') target = choices[(index + choices.length - 1) % choices.length];
      else if (event.key === 'Home') target = choices[0];
      else if (event.key === 'End') target = choices[choices.length - 1];
      else if (event.key === 'Escape') { event.preventDefault(); closeMenu(true); return; }
      if (target) { event.preventDefault(); target.focus({preventScroll:true}); }
    });
  });
  document.addEventListener('pointerdown', event => {
    if (!root.contains(event.target)) closeMenu(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && root.classList.contains('is-open')) closeMenu(true);
  });
  root.addEventListener('focusout', event => {
    if (!root.contains(event.relatedTarget)) closeMenu(false);
  });
  // Apply saved language on initial paint; never launch a splash screen on initial load.
  translate();
})();
