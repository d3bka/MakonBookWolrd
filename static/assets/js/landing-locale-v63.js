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
  const storyTranslations = {
  "eyebrow": {
    "en": "SATMAKON · STUDENT STORIES",
    "ru": "SATMAKON · ИСТОРИИ УЧЕНИКОВ",
    "uz": "SATMAKON · O‘QUVCHILAR FIKRLARI"
  },
  "heading-lead": {
    "en": "What our students",
    "ru": "Что говорят",
    "uz": "O‘quvchilarimiz"
  },
  "heading-accent": {
    "en": "say",
    "ru": "наши ученики",
    "uz": "nima deydi"
  },
  "intro": {
    "en": "Student feedback and results published by SATMakon.",
    "ru": "Отзывы учеников и результаты, опубликованные SATMakon.",
    "uz": "SATMakon saytida e’lon qilingan o‘quvchilar fikrlari va natijalari."
  },
  "university-caption": {
    "en": "Our students have entered top universities",
    "ru": "Наши ученики поступили в ведущие университеты",
    "uz": "O‘quvchilarimiz top universitetlarga kirishdi"
  },
  "quote-1": {
    "en": "“Thirty minutes a day with the vocabulary trainer and AI tutor helped me gain 250 points in Reading in three months.”",
    "ru": "«Тридцать минут в день со словарным тренажёром и AI-тьютором — и за три месяца мой Reading вырос на 250 баллов».",
    "uz": "“Vokabular trenajori va AI tutor bilan har kuni 30 daqiqa — uch oyda Reading’da 250 ball oshdi.”"
  },
  "quote-2": {
    "en": "“Kam aka wasn’t just a teacher — he was a mentor. Nobody told me I could score 1600. He did, and I achieved it.”",
    "ru": "«Кам ака был не просто учителем, а наставником. Никто не говорил, что я могу набрать 1600. Он поверил в меня — и у меня получилось».",
    "uz": "“Kam aka shunchaki o‘qituvchi emas — mentor. 1600 olishim mumkin deb hech kim aytmagan edi, u aytdi va men oldim.”"
  },
  "quote-3": {
    "en": "“The small-group format changed everything. My teacher knew where I struggled and adapted each lesson. I recommend it.”",
    "ru": "«Формат маленьких групп изменил всё. Учитель понимал, где мне трудно, и адаптировал каждый урок. Рекомендую».",
    "uz": "“Kichik guruh formati — o‘yinni o‘zgartirdi. O‘qituvchim men qayerda qiynalayotganimni aniq bilardi va har darsni menga moslashtirardi. Tavsiya etaman.”"
  },
  "quote-4": {
    "en": "“SAT Makon gave me the confidence and skills to approach the SAT directly. Coaching and progress reports kept me on track.”",
    "ru": "«SAT Makon дал мне уверенность и навыки для подготовки к SAT. Наставничество и отчёты о прогрессе помогали не сбиваться с пути».",
    "uz": "“SAT Makon menga SAT ga to‘g‘ridan-to‘g‘ri yondashish uchun ishonch va ko‘nikma berdi. Coaching va progress hisobotlari meni yo‘ldan chiqarmadi.”"
  },
  "quote-5": {
    "en": "“I never thought I could get into a top university while studying in Tashkent. SAT Makon’s strategies and Kam aka’s personal support helped me enter NYU with a $35,000 scholarship.”",
    "ru": "«Я не верила, что из Ташкента смогу поступить в топовый университет. Благодаря стратегиям SAT Makon и личной поддержке Кам ака я поступила в NYU со стипендией $35 000».",
    "uz": "“Toshkentdan turib top universitetga kirishga ishonmagandim. SAT Makon strategiyalari va Kam akaning shaxsiy e’tibori tufayli NYU dan $35 000 stipendiya bilan oldim.”"
  },
  "quote-6": {
    "en": "“I raised my Math score from 720 to 800 thanks to Kam aka’s question strategies. Now I study Computer Science at MIT.”",
    "ru": "«Благодаря стратегиям решения задач Кам ака я поднял Math с 720 до 800. Теперь изучаю Computer Science в MIT».",
    "uz": "“Math bo‘yicha 720 dan 800 ga ko‘tarildim — Kam akaning question-strategiyasi tufayli. Endi MITda Computer Science o‘qiyman.”"
  },
  "quote-7": {
    "en": "“Reading was my hidden weakness. Two months of intensive lessons and weekly mocks helped me go from 380 to 770.”",
    "ru": "«Reading был моей скрытой слабостью. За два месяца интенсивных занятий и еженедельных пробников я выросла с 380 до 770».",
    "uz": "“Reading qismi yashirin dushmanim edi. 2 oylik intensiv mashg‘ulotlar va weekly mock testlar meni 380 dan 770 gacha ko‘tardi.”"
  },
  "quote-8": {
    "en": "“A new mock test every week and a clear analysis every Monday. I had never seen such an organized approach anywhere else.”",
    "ru": "«Каждую неделю новый пробник, каждый понедельник — понятный разбор. Такой организованной системы я больше нигде не видел».",
    "uz": "“Har hafta yangi mock test, har dushanba aniq tahlil. Bunday tartibli yo‘nalishni boshqa hech qayerda ko‘rmaganman.”"
  },
  "quote-9": {
    "en": "“I scored 1100 on my first mock and was devastated. Four months later I got 1530. SAT Makon gave my effort a system.”",
    "ru": "«На первом пробнике я набрала 1100 и очень расстроилась. Через четыре месяца — 1530. SAT Makon сделал мои усилия системными».",
    "uz": "“Birinchi mock’da 1100 oldim — yiqilib tushdim. 4 oydan keyin 1530. SAT Makon mehnatga tizim qo‘shdi.”"
  },
  "quote-10": {
    "en": "“The AP Calculus BC course was polished. I scored a 5 and earned first-year university math credit.”",
    "ru": "«Курс AP Calculus BC был отлично проработан. Я получил 5 баллов и зачёт по математике за первый курс университета».",
    "uz": "“AP Calculus BC dasturi sayqallangan. 5 ball oldim, universitetda birinchi yili matematikadan kredit oldim.”"
  },
  "quote-11": {
    "en": "“Essay support and application strategy made the biggest difference after the SAT. I got into Columbia on a full scholarship.”",
    "ru": "«Помощь с эссе и стратегией подачи документов стала решающей после SAT. Я поступила в Columbia на полную стипендию».",
    "uz": "“Essay yordami va ariza strategiyasi — bu SAT’dan keyingi eng katta farq. Columbia’ga to‘liq stipendiya bilan kirdim.”"
  },
  "quote-12": {
    "en": "“I studied online from Nukus. I felt no difference — I received the same attention as in a classroom.”",
    "ru": "«Я училась онлайн из Нукуса. Разницы не почувствовала: внимания было столько же, сколько на очных занятиях».",
    "uz": "“Onlayn formatda Nukusdan o‘qidim. Hech qanday farq sezmadim — xuddi sinfda bo‘lgandek e’tibor.”"
  }
};
  const html = document.documentElement;
  const trigger = document.querySelector('[data-mb63-lang-trigger]');
  const menuRoot = document.querySelector('[data-mb63-locale]');
  const label = document.querySelector('[data-mb63-lang-current]');
  const choices = Array.from(document.querySelectorAll('[data-mb63-lang-option]'));
  if (!trigger || !menuRoot || !choices.length) return;
  const isValid = value => ['en', 'ru', 'uz'].includes(value);
  let stored;
  try { stored = window.localStorage.getItem(KEY); } catch (_) { stored = null; }
  const browser = (navigator.languages && navigator.languages[0] || navigator.language || 'en').toLowerCase().split('-')[0];
  let lang = isValid(stored) ? stored : (isValid(browser) ? browser : 'en');
  const originalText = new WeakMap();
  let busy = false;
  let scanning = false;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  function refreshNode(node) {
    if (node.nodeType !== Node.TEXT_NODE || !node.parentElement) return;
    if (node.parentElement.closest('script,style,textarea,option,[data-no-locale],.mb63-locale,[data-theme-switcher],[data-mbst-locale]')) return;
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
    const leading = original.match(/^\s*/)[0];
    const trailing = original.match(/\s*$/)[0];
    const nextText = leading + target + trailing;
    if (node.textContent !== nextText) node.textContent = nextText;
  }
  // Marked testimony text is also present in cloned carousel slides. Use stable keys
  // instead of the original DOM text, so repeated language changes update every copy.
  function translateStories(root) {
    if (!root || root.nodeType !== Node.ELEMENT_NODE) return;
    const elements = root.matches && root.matches('[data-mbst-locale]')
      ? [root] : [];
    root.querySelectorAll('[data-mbst-locale]').forEach(el => elements.push(el));
    for (const el of elements) {
      const variants = storyTranslations[el.getAttribute('data-mbst-locale')];
      if (variants && typeof variants[lang] === 'string' && el.textContent !== variants[lang]) {
        el.textContent = variants[lang];
      }
    }
  }
  function syncControls() {
    if (html.lang !== lang) html.lang = lang;
    if (label.textContent !== lang.toUpperCase()) label.textContent = lang.toUpperCase();
    choices.forEach(choice => {
      const selected = choice.dataset.mb63LangOption === lang;
      choice.setAttribute('aria-selected', selected ? 'true' : 'false');
      choice.tabIndex = selected ? 0 : -1;
    });
  }
  function apply() {
    if (scanning) return;
    scanning = true;
    syncControls();
    translateStories(document.body);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) refreshNode(node);
    // Update SEO/accessibility-visible text, not just the visible headline.
    const metadata = {
      en: ['MakonBook — SAT learning, testing & progress', 'SAT practice, mock exams, classrooms, vocabulary and progress in one workspace.'],
      ru: ['MakonBook — обучение, тесты и прогресс SAT', 'Практика SAT, пробные экзамены, классы, словарь и прогресс в одной платформе.'],
      uz: ['MakonBook — SAT ta’limi, testlar va natijalar', 'SAT mashqlari, sinov imtihonlari, sinflar, lug‘at va natijalar bitta platformada.']
    }[lang];
    document.title = metadata[0];
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', metadata[1]);
    scanning = false;
  }
  function openMenu(open) {
    menuRoot.classList.toggle('is-open', open);
    trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) {
      const selected = choices.find(choice => choice.dataset.mb63LangOption === lang);
      if (selected) selected.focus();
    }
  }
  trigger.addEventListener('click', () => openMenu(!menuRoot.classList.contains('is-open')));
  choices.forEach(choice => {
    choice.addEventListener('click', async () => {
      const next = choice.dataset.mb63LangOption;
      openMenu(false);
      trigger.focus({preventScroll:true});
      if (!isValid(next) || next === lang || busy) return;
      busy = true;
      const commit = () => {
        lang = next;
        try { window.localStorage.setItem(KEY, lang); } catch (_) {}
        apply();
      };
      try {
        const animator = window.MakonBookLandingTransition;
        if (animator && !reduceMotion.matches) await animator.run(commit);
        else commit();
      } catch (error) {
        console.error('[MakonBook] Unable to change landing language:', error);
        if (lang !== next) commit();
      } finally {
        busy = false;
      }
    });
  });
  document.addEventListener('pointerdown', event => {
    if (!menuRoot.contains(event.target)) openMenu(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') { openMenu(false); trigger.focus({preventScroll:true}); return; }
    if (!menuRoot.classList.contains('is-open')) return;
    const index = choices.indexOf(document.activeElement);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const step = event.key === 'ArrowDown' ? 1 : -1;
      choices[(index + step + choices.length) % choices.length].focus();
    }
  });
  menuRoot.addEventListener('focusout', event => {
    if (!menuRoot.contains(event.relatedTarget)) openMenu(false);
  });
  apply();
  // Dialogs for mock-exam registration are added dynamically by the existing code.
  // Translate only newly inserted nodes, and avoid self-triggering mutation loops.
  const observer = new MutationObserver(mutations => {
    // Only translate inserted content, never rescan the whole document in
    // response to our own text changes or the theme switcher updates.
    for (const mutation of mutations) {
      for (const added of mutation.addedNodes) {
        if (added.nodeType === Node.TEXT_NODE) refreshNode(added);
        else if (added.nodeType === Node.ELEMENT_NODE) {
          translateStories(added);
          const walker = document.createTreeWalker(added, NodeFilter.SHOW_TEXT);
          let node;
          while ((node = walker.nextNode())) refreshNode(node);
        }
      }
    }
  });
  observer.observe(document.body, {childList:true, subtree:true});
})();
