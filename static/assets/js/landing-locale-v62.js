/* MakonBook landing localization. Auto-select browser locale on first visit,
   then honor user's choice in localStorage; English remains the safe fallback.
   Translates customer-facing static copy without touching server-created data,
   URLs, attributes used by existing modal registration, or exam scores. */
(function () {
  'use strict';
  const KEY = 'makonbook.public.language.v62';
  const translations = {
    'Platform': ['Платформа', 'Platforma'], 'Results': ['Результаты', 'Natijalar'], 'Parents': ['Родителям', 'Ota-onalarga'], 'FAQ': ['Вопросы и ответы', 'Savol-javob'],
    'Mock exams': ['Пробные экзамены', 'Sinov imtihonlari'], 'Log in': ['Войти', 'Kirish'], 'Login': ['Войти', 'Kirish'],
    'SAT learning platform · built for progress': ['Платформа SAT для реального прогресса', 'Natija uchun yaratilgan SAT platformasi'],
    'One workspace.': ['Одна платформа.', 'Bitta platforma.'], 'Every SAT move.': ['Весь путь к SAT.', 'SAT sari har bir qadam.'],
    'Practice, review, vocabulary, classrooms and verified mock exams — connected in one focused MakonBook experience.': ['Практика, разбор заданий, словарь, классы и пробные экзамены — всё в одной платформе MakonBook.', 'Mashqlar, tahlil, lug‘at, sinflar va sinov imtihonlari — barchasi MakonBook platformasida.'],
    'Open MakonBook': ['Открыть MakonBook', 'MakonBook’ni ochish'], 'Check your level': ['Проверить свой уровень', 'Darajangizni tekshiring'],
    'Real exam flow': ['Реальный формат экзамена', 'Haqiqiy imtihon muhiti'], 'Timed, reviewed, protected': ['Таймер, проверка и защита', 'Vaqt, tekshiruv va himoya'],
    'Connected progress': ['Весь прогресс в одном месте', 'Barcha natijalar bir joyda'], 'Tests, classes, vocabulary': ['Тесты, занятия, словарь', 'Testlar, darslar, lug‘at'],
    'Family visibility': ['Контроль для родителей', 'Ota-onalar nazorati'], 'Parent statistics portal': ['Статистика для родителей', 'Ota-onalar statistikasi'],
    'Dashboard': ['Главная', 'Bosh sahifa'], 'Practice': ['Практика', 'Mashqlar'], 'Progress': ['Прогресс', 'Rivojlanish'], 'Classrooms': ['Классы', 'Sinflar'],
    'Vocabulary': ['Словарь', 'Lug‘at'], 'Ranking': ['Рейтинг', 'Reyting'], 'GOOD EVENING': ['ДОБРЫЙ ВЕЧЕР', 'XAYRLI KECH'],
    'Ready for the next level?': ['Готовы к следующему уровню?', 'Keyingi bosqichga tayyormisiz?'],
    'Current SAT path': ['Текущий SAT-прогресс', 'Hozirgi SAT natijasi'], '+40 this month': ['+40 за месяц', 'Bu oy +40'],
    'Strongest section': ['Сильная секция', 'Eng kuchli bo‘lim'], '12 questions to review': ['12 вопросов для разбора', 'Tahlil uchun 12 ta savol'],
    'Today': ['Сегодня', 'Bugun'], 'Vocabulary sprint': ['Словарный спринт', 'Lug‘at mashqi'], 'Study streak': ['Серия занятий', 'Uzluksiz o‘qish'],
    '12 days': ['12 дней', '12 kun'], 'Next mock': ['Следующий пробник', 'Keyingi sinov'], 'Seat verified': ['Место подтверждено', 'Joy tasdiqlangan'],
    'Digital SAT tests': ['Цифровые SAT-тесты', 'Raqamli SAT testlari'], 'Review': ['Разбор', 'Tahlil'],
    'Attempt history & analysis': ['История и анализ попыток', 'Urinishlar tarixi va tahlil'], 'Learn': ['Обучение', 'O‘rganish'],
    'Vocabulary & classrooms': ['Словарь и классы', 'Lug‘at va sinflar'], 'Verify': ['Подтверждение', 'Tasdiqlash'],
    'Mock exam registration': ['Запись на пробный экзамен', 'Sinov imtihoniga ro‘yxat'],
    'THE MAKONBOOK SYSTEM': ['СИСТЕМА MAKONBOOK', 'MAKONBOOK TIZIMI'], 'Less switching.': ['Меньше переключений.', 'Kamroq almashish.'],
    'More progress.': ['Больше прогресса.', 'Ko‘proq natija.'],
    'MakonBook is built around the real SAT workflow: learn something, test it, review the result, then know exactly what to do next.': ['MakonBook строится вокруг подготовки к SAT: изучить тему, решить задания, разобрать результат и понять следующий шаг.', 'MakonBook SAT tayyorgarligiga asoslanadi: mavzuni o‘rganing, test ishlang, natijani tahlil qiling va keyingi qadamni belgilang.'],
    'Practice that feels like the real test.': ['Практика как на настоящем экзамене.', 'Haqiqiy imtihondek mashq qiling.'],
    'Timed modules, reference tools, attempt history, review states and exam-integrity controls — without leaving the platform.': ['Модули с таймером, инструменты, история попыток, разбор и защита экзамена — всё на одной платформе.', 'Vaqtli modullar, vositalar, urinishlar tarixi, tahlil va imtihon himoyasi — barchasi bir joyda.'],
    'QUESTION 17 OF 27': ['ВОПРОС 17 ИЗ 27', '27 TADAN 17-SAVOL'], 'Which choice most logically completes the text?': ['Какой вариант логичнее всего дополняет текст?', 'Qaysi javob matnni mantiqan to‘ldiradi?'],
    'Know what moved your score.': ['Понимайте, почему меняется балл.', 'Ballingiz nega o‘zgarganini biling.'],
    'Turn every attempt into a useful next step with section-level and question-level review.': ['Разбирайте каждую попытку по секциям и вопросам, чтобы знать, что улучшать.', 'Har bir urinishni bo‘lim va savollar bo‘yicha tahlil qilib, nimani yaxshilashni biling.'],
    'Vocabulary that sticks.': ['Слова, которые запоминаются.', 'Esda qoladigan so‘zlar.'],
    'Personal decks, flashcards, quizzes and retention practice in the same student workspace.': ['Личные наборы слов, карточки, викторины и повторение — в одном кабинете.', 'Shaxsiy so‘zlar, kartochkalar, viktorinalar va takrorlash — bitta kabinetda.'],
    "TODAY'S WORD": ['СЛОВО ДНЯ', 'KUN SO‘ZI'], 'present, appearing, or found everywhere': ['присутствующий повсюду', 'hamma joyda uchraydigan'],
    'Classrooms stay connected to performance.': ['Занятия связаны с результатами.', 'Darslar natijalar bilan bog‘langan.'],
    'Lessons, homework, teacher materials and student tracking become part of the same progress picture.': ['Уроки, домашние задания, материалы и прогресс учеников объединены.', 'Darslar, uy vazifalari, materiallar va o‘quvchi natijalari birlashtirilgan.'],
    'Submitted': ['Отправлено', 'Topshirildi'], 'Homework': ['Домашние задания', 'Uy vazifalari'], 'Attendance': ['Посещаемость', 'Davomat'], 'Teacher notes': ['Заметки учителя', 'Ustoz izohlari'],
    'UPCOMING MOCK EXAMS': ['БЛИЖАЙШИЕ ПРОБНЫЕ ЭКЗАМЕНЫ', 'YAKINLASHAYOTGAN SINOV IMTIHONLARI'], 'Reserve the seat.': ['Забронируйте место.', 'Joyingizni band qiling.'],
    'We handle the rest.': ['Остальное — за нами.', 'Qolganini biz bajarib beramiz.'],
    'Email verification, capacity protection and a saved registration ID keep the whole process clear before exam day.': ['Подтверждение почты, контроль мест и регистрационный номер делают запись понятной.', 'Email tasdig‘i, joylarni nazorat qilish va ro‘yxat IDsi jarayonni osonlashtiradi.'],
    'No registration window is open right now.': ['Сейчас запись на экзамены закрыта.', 'Hozir ro‘yxatdan o‘tish yopiq.'],
    'Check all mock exams ↗': ['Посмотреть все пробники ↗', 'Barcha sinovlar ↗'], 'Looking for every available mock exam?': ['Ищете все доступные пробные экзамены?', 'Barcha sinov imtihonlarini izlayapsizmi?'],
    'Open all mock exams ↗': ['Открыть все пробники ↗', 'Barcha sinovlarni ko‘rish ↗'],
    'ONE PLATFORM · THREE VIEWS': ['ОДНА ПЛАТФОРМА · ТРИ КАБИНЕТА', 'BITTA PLATFORMA · UCHTA KABINET'],
    'Made for everyone': ['Создано для всех', 'Barcha uchun yaratilgan'], 'around the student.': ['вокруг ученика.', 'o‘quvchi atrofida.'],
    'Different people need different information. MakonBook keeps each workspace focused instead of putting every tool on every screen.': ['Ученикам, преподавателям и родителям нужна разная информация. MakonBook показывает каждому только нужные инструменты.', 'O‘quvchi, ustoz va ota-onaga turli ma’lumot kerak. MakonBook har biriga kerakli vositalarni ko‘rsatadi.'],
    'STUDENT': ['УЧЕНИК', 'O‘QUVCHI'], 'Your complete SAT workspace.': ['Ваш кабинет подготовки к SAT.', 'SAT uchun shaxsiy kabinetingiz.'],
    'Practice, review, vocabulary, homework, classroom activity and progress.': ['Практика, разбор, словарь, домашние задания, классы и прогресс.', 'Mashqlar, tahlil, lug‘at, uy vazifalari, sinflar va natijalar.'],
    'Open student workspace ↗': ['Открыть кабинет ученика ↗', 'O‘quvchi kabineti ↗'],
    'TEACHER & STAFF': ['УЧИТЕЛЯ И СОТРУДНИКИ', 'USTOZLAR VA XODIMLAR'],
    'Teach with the full picture.': ['Обучайте, видя общую картину.', 'Natijalarni kuzatib dars bering.'],
    'Classrooms, assignments, materials and student performance in one operational workspace.': ['Классы, задания, материалы и результаты учеников в одном кабинете.', 'Sinflar, topshiriqlar, materiallar va natijalar bir kabinetda.'],
    'Sign in to staff workspace ↗': ['Войти в кабинет преподавателя ↗', 'Ustoz kabinetiga kirish ↗'],
    'PARENTS': ['РОДИТЕЛИ', 'OTA-ONALAR'], 'See progress without entering the classroom.': ['Следите за прогрессом без посещения урока.', 'Darsga kirmasdan natijani kuzating.'],
    "Use the student's registration number to open a clear statistics view that stays remembered on the device.": ['Введите номер регистрации ученика, чтобы открыть его статистику на устройстве.', 'O‘quvchi ro‘yxat raqami orqali statistikani qurilmangizda oching.'],
    'Open parent portal ↗': ['Открыть портал родителей ↗', 'Ota-onalar portalini ochish ↗'],
    'Quick answers.': ['Быстрые ответы.', 'Tezkor javoblar.'], 'No dead ends.': ['Ничего лишнего.', 'Ortiqcha savollarga o‘rin yo‘q.'],
    'Everything important about accounts, mock registration, parent access and score tracking — without sending you through extra pages.': ['Ответы об аккаунте, пробных экзаменах, доступе родителей и оценках — на одной странице.', 'Akkaunt, sinovlar, ota-onalar kirishi va natijalar bo‘yicha javoblar bir sahifada.'],
    'Do SATMakon students need a separate mock-exam account?': ['Нужен ли ученику SATMakon отдельный аккаунт для пробников?', 'SATMakon o‘quvchisiga sinov uchun alohida akkaunt kerakmi?'],
    'No. Choose “I study at SATMakon”, enter your MakonBook username and password, then verify the email linked to your account. The whole flow stays on the current page.': ['Нет. Выберите «Я учусь в SATMakon», введите логин и пароль MakonBook и подтвердите почту. Всё проходит на этой странице.', 'Yo‘q. «SATMakonda o‘qiyman»ni tanlang, MakonBook login va parolingizni kiriting, emailingizni tasdiqlang. Hammasi shu sahifada.'],
    'Will I have to register again after refreshing?': ['Нужно ли регистрироваться повторно после обновления страницы?', 'Sahifa yangilangandan keyin qayta ro‘yxatdan o‘tish kerakmi?'],
    'After a successful verification, the registration is remembered on that browser. Reopening the same mock exam shows the confirmed state instead of restarting the form.': ['После подтверждения браузер запоминает регистрацию. При повторном открытии пробника вы увидите её статус.', 'Tasdiqlangandan so‘ng brauzer ro‘yxatni eslab qoladi. Sinovni qayta ochganingizda tasdiqlangan holat ko‘rsatiladi.'],
    'What can parents see?': ['Что могут видеть родители?', 'Ota-onalar nimani ko‘ra oladi?'],
    "The parent portal uses the student's registration number to show a focused statistics view, including rating data and recent assessment history where available.": ['Родительский портал показывает оценки, рейтинг и историю оценивания после подтверждения доступа.', 'Ota-onalar portali kirish tasdiqlangandan keyin baholar, reyting va baholash tarixini ko‘rsatadi.'],
    'Are the score cards live student results?': ['Карточки баллов — реальные результаты учеников?', 'Ball kartalari haqiqiy o‘quvchi natijalarimi?'],
    'They mirror selected SATMakon results already published publicly. The block is presented as SATMakon outcomes rather than claiming MakonBook alone produced those scores.': ['Это отдельные публичные результаты SATMakon. Они не означают, что баллы получены исключительно благодаря MakonBook.', 'Bular SATMakonning avval e’lon qilingan natijalari. Ballar faqat MakonBook tufayli olingani da’vo qilinmaydi.'],
    'YOUR NEXT MOVE': ['ВАШ СЛЕДУЮЩИЙ ШАГ', 'KEYINGI QADAM'], 'Open MakonBook.': ['Откройте MakonBook.', 'MakonBook’ni oching.'],
    'Keep moving.': ['Продолжайте движение.', 'Olg‘a intiling.'], 'Your tests, classes and progress are already where they should be.': ['Все тесты, классы и результаты уже в одном месте.', 'Testlar, sinflar va natijalaringiz bir joyda.'],
    'Sign in to MakonBook ↗': ['Войти в MakonBook ↗', 'MakonBook’ga kirish ↗'], 'Browse mock exams': ['Смотреть пробники', 'Sinovlarni ko‘rish'],
    'The SAT workspace for learning, testing and measurable progress.': ['Единая SAT-платформа для обучения, тестирования и прогресса.', 'SAT o‘rganish, test va natijalar platformasi.'],
    'Top': ['Наверх', 'Yuqoriga'],
  };
  const html = document.documentElement;
  const select = document.querySelector('[data-mb62-lang-select]');
  if (!select) return;
  const isValid = value => ['en', 'ru', 'uz'].includes(value);
  let stored;
  try { stored = window.localStorage.getItem(KEY); } catch (_) { stored = null; }
  const browser = (navigator.languages && navigator.languages[0] || navigator.language || 'en').toLowerCase().split('-')[0];
  let lang = isValid(stored) ? stored : (isValid(browser) ? browser : 'en');
  const originalText = new WeakMap();
  function refreshNode(node) {
    if (node.nodeType !== Node.TEXT_NODE || !node.parentElement) return;
    if (node.parentElement.closest('script,style,textarea,option,[data-no-locale]')) return;
    let original = originalText.get(node);
    if (original === undefined) {
      const content = node.textContent;
      const key = content.trim();
      if (!translations[key]) return;
      original = content;
      originalText.set(node, original);
    }
    const key = original.trim();
    const target = lang === 'en' ? key : (translations[key] || [])[lang === 'ru' ? 0 : 1] || key;
    const leading = original.match(/^\s*/)[0], trailing = original.match(/\s*$/)[0];
    const newText = leading + target + trailing;
    if (node.textContent !== newText) node.textContent = newText;
  }
  let scanning = false;
  function apply() {
    if (scanning) return;
    scanning = true;
    html.lang = lang;
    select.value = lang;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) refreshNode(node);
    scanning = false;
  }
  select.addEventListener('change', function () {
    if (!isValid(select.value)) return;
    lang = select.value;
    try { window.localStorage.setItem(KEY, lang); } catch (_) {}
    apply();
  });
  apply();
  // Mock registration produces new DOM after load; localize it if copy matches.
  const observer = new MutationObserver(() => apply());
  observer.observe(document.body, {childList:true, subtree:true});
})();
