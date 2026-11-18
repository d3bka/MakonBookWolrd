/* MakonBook V85 public pages: header, mobile menu, EN/RU/UZ text, holiday decor, reveal.
   Language: ?lang= → saved choice → browser language → English. Elements carry
   data-i18n="key" (text), data-i18n-placeholder and data-i18n-aria. The English text
   stays in the HTML, so the page reads fine without JavaScript. */
(function () {
  'use strict';
  var KEY = 'makonbook.public.language.v62';
  var LANGS = ['en', 'ru', 'uz'];

  // key: [ru, uz]  (English comes from the HTML)
  var T = {
    'nav.platform': ['Платформа', 'Platforma'],
    'nav.courses': ['Курсы', 'Kurslar'],
    'nav.results': ['Результаты', 'Natijalar'],
    'nav.parents': ['Родителям', 'Ota-onalarga'],
    'nav.mocks': ['Пробные экзамены', 'Sinov imtihonlari'],
    'nav.faq': ['Вопросы', 'Savollar'],
    'nav.open': ['Открыть MakonBook', 'MakonBook’ni ochish'],
    'nav.login': ['Войти', 'Kirish'],
    'nav.signup': ['Регистрация', 'Ro‘yxatdan o‘tish'],
    'nav.level': ['Проверить уровень', 'Darajani tekshirish'],
    'nav.skip': ['Перейти к содержанию', 'Asosiy qismga o‘tish'],
    'nav.menu': ['Открыть меню', 'Menyuni ochish'],

    'footer.about': ['SAT-платформа SATMakon: практика, работа над ошибками, поступление и прогресс в одном месте.', 'SATMakon’ning SAT platformasi: mashqlar, xatolar ustida ishlash, qabul va natijalar bir joyda.'],
    'footer.students': ['Ученикам', 'O‘quvchilarga'],
    'footer.platform': ['Платформа', 'Platforma'],
    'footer.features': ['Возможности', 'Imkoniyatlar'],
    'footer.help': ['Родителям и помощь', 'Ota-onalar va yordam'],
    'footer.parent_portal': ['Портал для родителей', 'Ota-onalar portali'],
    'footer.city': ['Ташкент, Узбекистан', 'Toshkent, O‘zbekiston'],

    'hero.badge_new': ['НОВОЕ', 'YANGI'],
    'hero.badge': ['Видеокурс по поступлению · 187 университетов', 'Qabul bo‘yicha video kurs · 187 universitet'],
    'hero.title1': ['Твой балл SAT —', 'SAT balingiz —'],
    'hero.title2': ['шаг за шагом.', 'qadam-baqadam.'],
    'hero.lead': ['Практика Digital SAT, которая помнит каждую ошибку, курс по поступлению от преподавателей SATMakon и прогресс, который видят родители, — всё в MakonBook.', 'Har bir xatoni eslab qoladigan Digital SAT mashqlari, SATMakon ustozlaridan qabul kursi va ota-onalar ko‘radigan natijalar — barchasi MakonBook’da.'],
    'hero.cta_signup': ['Создать бесплатный аккаунт', 'Bepul akkaunt ochish'],
    'hero.note': ['Уже учишься в SATMakon?', 'SATMakon’da o‘qiysizmi?'],
    'hero.stat1': ['полные пробные тесты', 'to‘liq sinov testlari'],
    'hero.stat2': ['видеоуроков по поступлению', 'qabul bo‘yicha video dars'],
    'hero.stat3': ['университетов с баллами SAT', 'SAT ballari bilan universitet'],
    'mock.path': ['Твой путь в SAT', 'SAT yo‘lingiz'],
    'mock.growth': ['+40 за месяц', 'oyiga +40'],
    'mock.rw': ['12 вопросов на разбор', '12 ta savol tahlilga'],
    'mock.math': ['Самая сильная секция', 'Eng kuchli bo‘lim'],
    'mock.mistakes': ['Ошибки для исправления', 'Tuzatiladigan xatolar'],
    'mock.m1': ['Переходы', 'Bog‘lovchilar'],
    'mock.m2': ['Линейные уравнения', 'Chiziqli tenglamalar'],
    'mock.m3': ['Окружности', 'Aylanalar'],
    'mock.retry': ['Решить', 'Qayta'],
    'mock.fixed': ['Исправлено ✓', 'Tuzatildi ✓'],
    'mock.lesson_label': ['Поступление · урок 12', 'Qabul · 12-dars'],
    'mock.lesson': ['Мотивационное эссе', 'Shaxsiy esse'],
    'mock.uni_label': ['Для твоего балла', 'Balingiz uchun'],
    'mock.uni': ['NYU · Подходит', 'NYU · Mos'],

    'trust.title': ['Ученики SATMakon учатся в', 'SATMakon o‘quvchilari o‘qiydi:'],
    'features.kicker': ['Платформа', 'Platforma'],
    'features.title': ['Всё для SAT. В одном месте.', 'SAT uchun hammasi. Bir joyda.'],
    'features.lead': ['Учись, решай тесты, разбирай ошибки и планируй поступление без десятка разных приложений.', 'O‘qing, test yeching, xatolarni tahlil qiling va qabulni rejalashtiring — o‘nta ilovasiz.'],
    'f.free': ['Бесплатно →', 'Bepul →'],
    'f1.t': ['Пробные тесты', 'Sinov testlari'],
    'f1.p': ['Полные тесты Digital SAT с настоящим таймером, двумя модулями и мгновенным результатом.', 'Haqiqiy taymer, ikki modul va darhol natija bilan to‘liq Digital SAT testlari.'],
    'f2.t': ['Ошибки', 'Xatolar'],
    'f2.p': ['Каждый неверный или пропущенный ответ попадает в «Ошибки». Реши заново — один верный ответ, и ошибка исправлена.', 'Har bir noto‘g‘ri yoki o‘tkazib yuborilgan javob «Xatolar»ga tushadi. Qayta yeching — bitta to‘g‘ri javob va xato tuzatildi.'],
    'f3.t': ['Курс по поступлению от SATMakon', 'SATMakon’dan qabul kursi'],
    'f3.p': ['28 видеоуроков: выбор университетов, Common App, эссе, стипендии, Великобритания, Турция и Азия — с премиум-материалами для учеников SATMakon.', '28 ta video dars: universitet tanlash, Common App, esse, grantlar, Buyuk Britaniya, Turkiya va Osiyo — SATMakon o‘quvchilari uchun premium materiallar bilan.'],
    'f3.tag': ['Первые 3 урока бесплатно →', 'Dastlabki 3 dars bepul →'],
    'f4.t': ['Университеты', 'Universitetlar'],
    'f4.p': ['187 университетов с диапазонами SAT, ценами и финпомощью. Узнай, где у тебя reach, match или safety.', 'SAT oralig‘i, narxlar va moliyaviy yordam bilan 187 universitet. Balingizga ko‘ra reach, match yoki safety.'],
    'f5.t': ['Словарь', 'Lug‘at'],
    'f5.p': ['Списки слов, карточки и квизы по словам, которые действительно встречаются в SAT.', 'SAT’da haqiqatan uchraydigan so‘zlar uchun ro‘yxatlar, kartochkalar va testlar.'],
    'f6.t': ['Классы и домашние задания', 'Sinflar va uy vazifalari'],
    'f6.p': ['Уроки, домашние задания и отзывы преподавателя твоей группы SATMakon — рядом с практикой.', 'SATMakon guruhingizdagi darslar, uy vazifalari va ustoz fikri — mashqlar yonida.'],
    'f6.tag': ['Для учеников SATMakon →', 'SATMakon o‘quvchilari uchun →'],
    'f7.t': ['Прогресс и MakonRoom', 'Natijalar va MakonRoom'],
    'f7.p': ['История баллов, слабые темы, XP, серии и своя учебная комната, которая держит в тонусе.', 'Ballar tarixi, zaif mavzular, XP, ketma-ketlik va sizni olg‘a undaydigan o‘quv xonangiz.'],

    'steps.kicker': ['Как это работает', 'Qanday ishlaydi'],
    'steps.title': ['Начни за три шага.', 'Uch qadamda boshlang.'],
    'steps.lead': ['Без звонков и бумаг: всё начинается онлайн и занимает пару минут.', 'Qo‘ng‘iroq va hujjatlarsiz: hammasi onlayn boshlanadi va bir necha daqiqa oladi.'],
    's1.t': ['Зарегистрируйся по почте', 'Pochta orqali ro‘yxatdan o‘ting'],
    's1.p': ['Подтверди 6-значный код из письма — и аккаунт готов.', 'Xatdagi 6 xonali kodni tasdiqlang — akkaunt tayyor.'],
    's2.t': ['Проверь уровень', 'Darajangizni tekshiring'],
    's2.p': ['Бесплатная проверка уровня покажет отдельный балл по Reading & Writing и по Math.', 'Bepul daraja testi Reading & Writing va Math bo‘yicha alohida ball ko‘rsatadi.'],
    's3.t': ['Решай и исправляй ошибки', 'Yeching va xatolarni tuzating'],
    's3.p': ['Решай тесты, исправляй каждую ошибку и смотри, как растёт балл неделя за неделей.', 'Test yeching, har bir xatoni tuzating va balingiz haftama-hafta o‘sishini kuzating.'],

    'courses.kicker': ['Курсы SATMakon', 'SATMakon kurslari'],
    'courses.title': ['Учись с преподавателями SATMakon. В классе или онлайн.', 'SATMakon ustozlari bilan o‘qing. Sinfda yoki onlayn.'],
    'courses.lead': ['Ученики SATMakon получают весь MakonBook: все тесты, свои классы, домашние задания и весь курс по поступлению.', 'SATMakon o‘quvchilari butun MakonBook’ni oladi: barcha testlar, sinflar, uy vazifalari va to‘liq qabul kursi.'],
    'courses.ask': ['Спросить в Telegram', 'Telegram’da so‘rash'],
    'c1.pill': ['Офлайн · Ташкент', 'Oflayn · Toshkent'],
    'c1.t': ['Занятия в небольшой группе', 'Kichik guruhda darslar'],
    'c1.l1': ['Небольшие группы с преподавателем SATMakon', 'SATMakon ustozi bilan kichik guruhlar'],
    'c1.l2': ['Регулярные пробные экзамены в условиях реального теста', 'Haqiqiy imtihon sharoitida muntazam sinov imtihonlari'],
    'c1.l3': ['Домашние задания и прогресс в MakonBook', 'Uy vazifalari va natijalar MakonBook’da'],
    'c1.l4': ['Родители видят посещаемость и результаты', 'Ota-onalar davomat va natijalarni ko‘radi'],
    'c2.pill': ['Онлайн', 'Onlayn'],
    'c2.t': ['Живые занятия из любого места', 'Istalgan joydan jonli darslar'],
    'c2.l1': ['Живые уроки с преподавателями SATMakon', 'SATMakon ustozlari bilan jonli darslar'],
    'c2.l2': ['Те же материалы, пробные экзамены и доступ к MakonBook', 'Xuddi shu materiallar, sinov imtihonlari va MakonBook'],
    'c2.l3': ['Балл по каждому предмету до начала занятий', 'Darslardan oldin har bir fan bo‘yicha ball'],
    'c2.l4': ['Учись из любого города', 'Istalgan shahardan o‘qing'],

    'results.kicker': ['Результаты', 'Natijalar'],
    'results.title': ['Ученики SATMakon. Настоящие истории.', 'SATMakon o‘quvchilari. Haqiqiy hikoyalar.'],
    'results.lead': ['Баллы и поступления, опубликованные SATMakon.', 'SATMakon e’lon qilgan ballar va qabullar.'],

    'parents.kicker': ['Родителям', 'Ota-onalarga'],
    'parents.title': ['Прогресс без догадок.', 'Natijalar — taxminsiz.'],
    'parents.lead': ['Портал для родителей показывает, как ваш ребёнок учится в SATMakon, — откройте его по номеру телефона ученика.', 'Ota-onalar portali farzandingiz SATMakon’da qanday o‘qiyotganini ko‘rsatadi — o‘quvchining telefon raqami bilan oching.'],
    'parents.l1': ['Посещаемость и оценки за уроки', 'Davomat va dars baholari'],
    'parents.l2': ['Баллы за тесты и их динамика', 'Test ballari va ularning o‘zgarishi'],
    'parents.l3': ['Домашние задания, сданные вовремя', 'O‘z vaqtida bajarilgan uy vazifalari'],
    'parents.cta': ['Открыть портал для родителей', 'Ota-onalar portalini ochish'],
    'parents.card': ['Обзор недели', 'Haftalik ko‘rinish'],
    'parents.r1': ['Посещаемость', 'Davomat'],
    'parents.r2': ['Последний пробный экзамен', 'Oxirgi sinov imtihoni'],
    'parents.r3': ['Домашние задания', 'Uy vazifalari'],
    'parents.r4': ['Оценка преподавателя', 'Ustoz bahosi'],

    'mocks.kicker': ['Пробные экзамены', 'Sinov imtihonlari'],
    'mocks.title': ['Настоящий экзамен. До настоящего экзамена.', 'Haqiqiy imtihon kuni. Haqiqiy imtihondan oldin.'],
    'mocks.lead': ['Запишись на подтверждённое место и сдай полный Digital SAT в условиях реального экзамена.', 'Tasdiqlangan joyga yoziling va to‘liq Digital SAT’ni haqiqiy sharoitda topshiring.'],
    'mocks.seats': ['МЕСТА', 'JOYLAR'],
    'mocks.empty': ['Сейчас запись не открыта.', 'Hozir ro‘yxatga olish ochiq emas.'],
    'mocks.all': ['Все пробные экзамены ↗', 'Barcha sinov imtihonlari ↗'],

    'faq.title': ['Быстрые ответы.', 'Tezkor javoblar.'],
    'faq.lead': ['Остался вопрос? Напишите SATMakon в Telegram.', 'Savolingiz qoldimi? SATMakon’ga Telegram’da yozing.'],
    'q1.q': ['MakonBook бесплатный?', 'MakonBook bepulmi?'],
    'q1.a': ['Да. Создайте бесплатный аккаунт по почте: пробные тесты, «Ошибки», словарь, каталог университетов и первые уроки по поступлению открыты. Ученикам SATMakon доступно всё.', 'Ha. Pochta orqali bepul akkaunt oching: sinov testlari, «Xatolar», lug‘at, universitetlar katalogi va qabul kursining dastlabki darslari ochiq. SATMakon o‘quvchilariga hammasi ochiq.'],
    'q2.q': ['Я учусь в SATMakon. Как получить полный доступ?', 'SATMakon’da o‘qiyman. To‘liq kirishni qanday olaman?'],
    'q2.a': ['Зарегистрируйтесь по почте, выберите «Я учусь в SATMakon» и подтвердите номер телефона, который есть у SATMakon, кодом из SMS. Классы, домашние задания и вся библиотека откроются сразу.', 'Pochta orqali ro‘yxatdan o‘ting, «SATMakon’da o‘qiyman»ni tanlang va SATMakon’dagi telefon raqamingizni SMS kod bilan tasdiqlang. Sinflar, uy vazifalari va butun kutubxona darhol ochiladi.'],
    'q3.q': ['Как проверить свой уровень?', 'Darajamni qanday tekshiraman?'],
    'q3.a': ['Пройдите бесплатную проверку уровня: Reading & Writing и Math, с отдельным баллом по каждому предмету. Аккаунт не нужен.', 'Bepul daraja testini topshiring: Reading & Writing va Math, har bir fan bo‘yicha alohida ball. Akkaunt shart emas.'],
    'q4.q': ['Нужен ли аккаунт для пробного экзамена?', 'Sinov imtihoni uchun akkaunt kerakmi?'],
    'q4.a': ['Нет. Запишитесь на место по почте. Ученики SATMakon могут записаться через свой вход в MakonBook.', 'Yo‘q. Pochta orqali joy band qiling. SATMakon o‘quvchilari MakonBook login’i bilan yozilishi mumkin.'],
    'q5.q': ['Что видят родители?', 'Ota-onalar nimani ko‘radi?'],
    'q5.a': ['Посещаемость, оценки за уроки, результаты тестов и домашние задания — по номеру телефона ученика.', 'Davomat, dars baholari, test natijalari va uy vazifalari — o‘quvchining telefon raqami orqali.'],
    'q6.q': ['Результаты на этой странице настоящие?', 'Bu sahifadagi natijalar haqiqiymi?'],
    'q6.a': ['Да: это результаты учеников SATMakon, которые опубликовал SATMakon.', 'Ha: bular SATMakon e’lon qilgan SATMakon o‘quvchilarining natijalari.'],
    'final.title': ['Начни готовиться сегодня.', 'Bugun tayyorlanishni boshlang.'],
    'final.lead': ['Бесплатный аккаунт, настоящая практика Digital SAT и понятный план к твоему баллу.', 'Bepul akkaunt, haqiqiy Digital SAT mashqlari va balingizga aniq reja.'],

    /* auth */
    'auth.kicker': ['Аккаунт MakonBook', 'MakonBook akkaunti'],
    'auth.login_title': ['Продолжай с того места, где остановился.', 'Qolgan joyingizdan davom eting.'],
    'auth.login_lead': ['Тесты, ошибки, классы, словарь и прогресс — в одном аккаунте.', 'Testlar, xatolar, sinflar, lug‘at va natijalar — bitta akkauntda.'],
    'auth.p1t': ['Практика и разбор', 'Mashq va tahlil'],
    'auth.p1': ['Тесты с таймером, продолжение попыток и разбор ошибок.', 'Taymerli testlar, urinishni davom ettirish va xatolar tahlili.'],
    'auth.p2t': ['Классы SATMakon', 'SATMakon sinflari'],
    'auth.p2': ['Уроки, домашние задания и материалы преподавателя.', 'Darslar, uy vazifalari va ustoz materiallari.'],
    'auth.p3t': ['Безопасный вход', 'Xavfsiz kirish'],
    'auth.p3': ['Почта, телефон или Google — как вам удобнее.', 'Pochta, telefon yoki Google — qaysi qulay bo‘lsa.'],
    'auth.welcome': ['С возвращением.', 'Xush kelibsiz.'],
    'auth.new': ['Впервые в MakonBook?', 'MakonBook’da yangimisiz?'],
    'auth.create': ['Создать бесплатный аккаунт', 'Bepul akkaunt ochish'],
    'auth.login_field': ['Почта, телефон или логин', 'Pochta, telefon yoki login'],
    'auth.login_ph': ['Введите логин', 'Login’ni kiriting'],
    'auth.password': ['Пароль', 'Parol'],
    'auth.password_ph': ['Введите пароль', 'Parolni kiriting'],
    'auth.show': ['Показать', 'Ko‘rsatish'],
    'auth.hide': ['Скрыть', 'Yashirish'],
    'auth.forgot': ['Забыли пароль?', 'Parolni unutdingizmi?'],
    'auth.login_btn': ['Войти в MakonBook', 'MakonBook’ga kirish'],
    'auth.or': ['или', 'yoki'],
    'auth.google': ['Продолжить с Google', 'Google orqali davom etish'],
    'auth.mocks_t': ['Запись на пробный экзамен', 'Sinov imtihoniga yozilish'],
    'auth.mocks_p': ['Место можно забронировать и без аккаунта.', 'Joyni akkauntsiz ham band qilish mumkin.'],
    'auth.parents_t': ['Портал для родителей', 'Ota-onalar portali'],
    'auth.parents_p': ['Статистика ученика по номеру телефона.', 'O‘quvchi statistikasi telefon raqami orqali.'],

    'reg.kicker': ['Бесплатный аккаунт', 'Bepul akkaunt'],
    'reg.side_title': ['Начни подготовку к SAT сегодня.', 'SAT’ga tayyorgarlikni bugun boshlang.'],
    'reg.side_lead': ['Аккаунт по почте за минуту: пробные тесты, «Ошибки», словарь, каталог университетов и первые уроки по поступлению — сразу.', 'Bir daqiqada pochta orqali akkaunt: sinov testlari, «Xatolar», lug‘at, universitetlar katalogi va qabul kursining dastlabki darslari — darhol.'],
    'reg.p1t': ['Ваши данные', 'Ma’lumotlaringiz'],
    'reg.p1': ['Имя, почта и пароль.', 'Ism, pochta va parol.'],
    'reg.p2t': ['Код на почту', 'Pochtaga kod'],
    'reg.p2': ['6-значный код подтвердит вашу почту.', '6 xonali kod pochtangizni tasdiqlaydi.'],
    'reg.p3t': ['Ученикам SATMakon', 'SATMakon o‘quvchilariga'],
    'reg.p3': ['Подключите аккаунт SATMakon кодом из SMS — откроются классы и всё остальное.', 'SATMakon akkauntini SMS kod bilan ulang — sinflar va qolgan hammasi ochiladi.'],
    'reg.title': ['Создать аккаунт', 'Akkaunt ochish'],
    'reg.have': ['Уже есть аккаунт?', 'Akkauntingiz bormi?'],
    'reg.first': ['Имя', 'Ism'],
    'reg.last': ['Фамилия', 'Familiya'],
    'reg.email': ['Почта', 'Pochta'],
    'reg.password2': ['Повторите пароль', 'Parolni takrorlang'],
    'reg.hint': ['Минимум 8 символов.', 'Kamida 8 ta belgi.'],
    'reg.agree': ['Я согласен, что MakonBook хранит моё имя и почту для работы аккаунта.', 'MakonBook akkauntim ishlashi uchun ismim va pochtamni saqlashiga roziman.'],
    'reg.btn': ['Отправить код', 'Kodni yuborish'],
    'reg.satmakon': ['Учишься в SATMakon? После регистрации подключите свой аккаунт кодом из SMS.', 'SATMakon’da o‘qiysizmi? Ro‘yxatdan o‘tgach akkauntingizni SMS kod bilan ulang.'],

    'ver.kicker': ['Почти готово', 'Deyarli tayyor'],
    'ver.title': ['Проверьте почту.', 'Pochtangizni tekshiring.'],
    'ver.lead': ['Мы отправили 6-значный код на', '6 xonali kodni yubordik:'],
    'ver.lead2': ['Код действует 15 минут. Если письма нет, проверьте «Спам» и «Промоакции».', 'Kod 15 daqiqa amal qiladi. Xat bo‘lmasa, «Spam» va «Promo» bo‘limlarini tekshiring.'],
    'ver.step': ['Шаг 2 из 2', '2-qadam (2 tadan)'],
    'ver.card': ['Введите код.', 'Kodni kiriting.'],
    'ver.code': ['6-значный код', '6 xonali kod'],
    'ver.btn': ['Создать аккаунт', 'Akkaunt yaratish'],
    'ver.no': ['Нет письма?', 'Xat kelmadimi?'],
    'ver.resend': ['Отправить новый код', 'Yangi kod yuborish'],
    'ver.change': ['Изменить почту', 'Pochtani o‘zgartirish'],

    'fp.kicker': ['Восстановление доступа', 'Kirishni tiklash'],
    'fp.side_title': ['Верните доступ, не теряя прогресс.', 'Natijalarni yo‘qotmasdan kirishni tiklang.'],
    'fp.side_lead': ['Введите почту вашего аккаунта MakonBook — мы пришлём короткий код для сброса пароля.', 'MakonBook akkauntingiz pochtasini kiriting — parolni tiklash uchun qisqa kod yuboramiz.'],
    'fp.p1t': ['Почта', 'Pochta'],
    'fp.p1': ['Почта вашего аккаунта.', 'Akkauntingiz pochtasi.'],
    'fp.p2t': ['Код', 'Kod'],
    'fp.p2': ['Код действует 10 минут.', 'Kod 10 daqiqa amal qiladi.'],
    'fp.p3t': ['Новый пароль', 'Yangi parol'],
    'fp.p3': ['Задайте новый пароль и войдите снова.', 'Yangi parol o‘rnating va qayta kiring.'],
    'fp.title': ['Получить код', 'Kod olish'],
    'fp.lead': ['Если почта есть в MakonBook, мы отправим 6-значный код.', 'Pochta MakonBook’da bo‘lsa, 6 xonali kod yuboramiz.'],
    'fp.btn': ['Отправить код', 'Kodni yuborish'],
    'fp.back': ['Назад ко входу', 'Kirishga qaytish'],
    'fp.have_code': ['У меня уже есть код', 'Menda kod bor'],
    'rp.title': ['Новый пароль', 'Yangi parol'],
    'rp.lead': ['Введите почту, код из письма и новый пароль.', 'Pochta, xatdagi kod va yangi parolni kiriting.'],
    'rp.code': ['Код из письма', 'Xatdagi kod'],
    'rp.new': ['Новый пароль', 'Yangi parol'],
    'rp.new2': ['Повторите новый пароль', 'Yangi parolni takrorlang'],
    'rp.btn': ['Сменить пароль', 'Parolni almashtirish'],
    'rp.resend': ['Получить новый код', 'Yangi kod olish']
  };

  var doc = document;
  var html = doc.documentElement;
  var body = doc.body;
  var valid = function (v) { return LANGS.indexOf(v) !== -1; };
  var store = {
    get: function () { try { return window.localStorage.getItem(KEY); } catch (_) { return null; } },
    set: function (v) { try { window.localStorage.setItem(KEY, v); } catch (_) {} }
  };

  /* ------------------------------------------------ season / holiday on old pages */
  var header = doc.querySelector('[data-mbp-header]');
  if (header && body) {
    if (!body.hasAttribute('data-season') && header.dataset.season) body.setAttribute('data-season', header.dataset.season);
    if (!body.hasAttribute('data-festive') && header.dataset.festive) body.setAttribute('data-festive', header.dataset.festive);
  }

  /* ------------------------------------------------ language */
  var parentRoot = doc.querySelector('[data-mb642-parent-locale]');
  function detect() {
    var q = null;
    try { q = new URL(window.location.href).searchParams.get('lang'); } catch (_) {}
    if (valid(q)) return q;
    if (parentRoot) {
      var htmlLang = (html.lang || 'en').toLowerCase().split('-')[0];
      var s0 = store.get();
      return valid(s0) ? s0 : (valid(htmlLang) ? htmlLang : 'en');
    }
    var s = store.get();
    if (valid(s)) return s;
    var nav = ((navigator.languages && navigator.languages[0]) || navigator.language || 'en').toLowerCase().split('-')[0];
    return valid(nav) ? nav : 'en';
  }
  var lang = detect();

  function tr(key, el, attr) {
    var holder = 'i18nEn' + (attr ? attr.replace(/[^a-z]/gi, '') : '');
    if (el.dataset[holder] === undefined) el.dataset[holder] = attr ? (el.getAttribute(attr) || '') : el.textContent;
    var en = el.dataset[holder];
    if (lang === 'en' || !T[key]) return en;
    return T[key][lang === 'ru' ? 0 : 1] || en;
  }

  function apply() {
    if (!parentRoot) html.lang = lang;
    doc.querySelectorAll('[data-i18n]').forEach(function (el) {
      var v = tr(el.getAttribute('data-i18n'), el);
      if (el.textContent !== v) el.textContent = v;
    });
    doc.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
      el.setAttribute('placeholder', tr(el.getAttribute('data-i18n-placeholder'), el, 'placeholder'));
    });
    doc.querySelectorAll('[data-i18n-aria]').forEach(function (el) {
      el.setAttribute('aria-label', tr(el.getAttribute('data-i18n-aria'), el, 'aria-label'));
    });
    // Testimonials (also in cloned carousel slides).
    var stories = window.MakonPublicStories;
    if (stories) {
      doc.querySelectorAll('[data-mbst-locale]').forEach(function (el) {
        var v = stories[el.getAttribute('data-mbst-locale')];
        if (v && typeof v[lang] === 'string' && el.textContent !== v[lang]) el.textContent = v[lang];
      });
    }
    // Holiday greeting.
    var g = doc.querySelector('[data-greeting]');
    if (g) {
      var t = g.querySelector('[data-greeting-text]');
      var text = g.getAttribute('data-' + lang) || g.getAttribute('data-en');
      if (t && text) t.textContent = text;
    }
    // Password toggles keep their state label.
    doc.querySelectorAll('[data-mbp-pass-toggle]').forEach(function (b) { labelToggle(b); });
    // Locale menu state.
    if (!parentRoot) {
      var cur = doc.querySelector('[data-mbp-locale] [data-mb63-lang-current]');
      if (cur) cur.textContent = lang.toUpperCase();
      doc.querySelectorAll('[data-mbp-locale] [data-mb63-lang-option]').forEach(function (o) {
        o.setAttribute('aria-selected', o.getAttribute('data-mb63-lang-option') === lang ? 'true' : 'false');
      });
    }
    try { window.dispatchEvent(new CustomEvent('makon:public-language', { detail: lang })); } catch (_) {}
    // Keep the language when moving between public pages that read ?lang (parent portal).
    doc.querySelectorAll('a[data-mb642-parent-link]').forEach(function (a) {
      try { var u = new URL(a.getAttribute('href'), window.location.href); u.searchParams.set('lang', lang); a.setAttribute('href', u.pathname + u.search + u.hash); } catch (_) {}
    });
  }

  var menuRoot = doc.querySelector('[data-mbp-locale]');
  if (menuRoot) {
    var trigger = menuRoot.querySelector('[data-mb63-lang-trigger]');
    var open = function (v) { menuRoot.classList.toggle('is-open', v); if (trigger) trigger.setAttribute('aria-expanded', v ? 'true' : 'false'); };
    if (trigger) trigger.addEventListener('click', function (e) { e.stopPropagation(); open(!menuRoot.classList.contains('is-open')); });
    menuRoot.querySelectorAll('[data-mb63-lang-option]').forEach(function (o) {
      o.addEventListener('click', function () {
        var next = o.getAttribute('data-mb63-lang-option');
        open(false);
        if (!valid(next) || next === lang) return;
        withBrand(function () { lang = next; store.set(lang); apply(); });
      });
    });
    doc.addEventListener('click', function (e) { if (!menuRoot.contains(e.target)) open(false); });
    doc.addEventListener('keydown', function (e) { if (e.key === 'Escape') open(false); });
  } else if (parentRoot) {
    // The parent portal script owns this menu; follow its choice for the shared header/footer.
    parentRoot.querySelectorAll('[data-mb63-lang-option]').forEach(function (o) {
      o.addEventListener('click', function () {
        var next = o.getAttribute('data-mb63-lang-option');
        if (valid(next)) { lang = next; setTimeout(apply, 0); }
      });
    });
  }

  /* ------------------------------------------------ brand transition (V87) */
  function bumpLogo() {
    doc.querySelectorAll('.mbp-brand-mark').forEach(function (mark) {
      mark.classList.remove('is-bump');
      void mark.offsetWidth;
      mark.classList.add('is-bump');
      setTimeout(function () { mark.classList.remove('is-bump'); }, 700);
    });
  }
  // Run `commit` under the full-screen MakonBook veil (makon-landing-transitions-v641-local.js).
  function withBrand(commit) {
    var fx = window.MakonBookLandingTransition;
    var done = function () { commit(); bumpLogo(); };
    if (fx && fx.run) fx.run(done).catch(done); else done();
  }
  // Theme choices: let the veil cover the switch, then replay the original click.
  doc.addEventListener('click', function (event) {
    var choice = event.target.closest && event.target.closest('[data-theme-choice]');
    if (!choice || choice.dataset.mbpReplay) return;
    var mode = choice.getAttribute('data-theme-choice');
    if (mode && mode === html.dataset.themeMode) return;
    event.preventDefault();
    event.stopPropagation();
    withBrand(function () {
      choice.dataset.mbpReplay = '1';
      try { choice.click(); } finally { delete choice.dataset.mbpReplay; }
    });
  }, true);

  /* ------------------------------------------------ header scroll + mobile menu */
  var closeMenu = function () {};
  if (header) {
    var onScroll = function () { header.classList.toggle('is-scrolled', window.scrollY > 8); };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    var burger = header.querySelector('[data-mbp-burger]');
    var mobile = doc.querySelector('[data-mbp-mobile]');
    if (burger && mobile) {
      var setMenu = function (v) {
        header.classList.toggle('is-open', v);
        mobile.classList.toggle('is-open', v);
        burger.setAttribute('aria-expanded', v ? 'true' : 'false');
        body.classList.toggle('mbp-menu-open', v);
      };
      closeMenu = function () { setMenu(false); };
      burger.addEventListener('click', function () { setMenu(!header.classList.contains('is-open')); });
      mobile.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', function () { setMenu(false); }); });
      doc.addEventListener('keydown', function (e) { if (e.key === 'Escape') setMenu(false); });
      window.addEventListener('resize', function () { if (window.innerWidth > 900) setMenu(false); });
    }
  }

  /* ------------------------------------------------ password show/hide */
  function labelToggle(b) {
    var input = doc.getElementById(b.getAttribute('aria-controls'));
    var shown = input && input.type === 'text';
    var en = shown ? 'Hide' : 'Show';
    var key = shown ? 'auth.hide' : 'auth.show';
    b.textContent = lang === 'en' ? en : T[key][lang === 'ru' ? 0 : 1];
    b.setAttribute('aria-pressed', shown ? 'true' : 'false');
  }
  doc.querySelectorAll('[data-mbp-pass-toggle]').forEach(function (b) {
    b.addEventListener('click', function () {
      var input = doc.getElementById(b.getAttribute('aria-controls'));
      if (!input) return;
      input.type = input.type === 'password' ? 'text' : 'password';
      labelToggle(b);
    });
  });

  /* ------------------------------------------------ one-time code input: digits only */
  doc.querySelectorAll('[data-mbp-code]').forEach(function (input) {
    input.addEventListener('input', function () {
      var v = input.value.replace(/\D/g, '').slice(0, 6);
      if (input.value !== v) input.value = v;
    });
  });

  /* ------------------------------------------------ falling decor */
  var layer = doc.querySelector('[data-festive-layer]');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (layer && !reduce && body && (body.getAttribute('data-festive') || body.getAttribute('data-season')) && !layer.children.length) {
    var frag = doc.createDocumentFragment();
    for (var i = 0; i < 18; i++) {
      var el = doc.createElement('i');
      var r = function (a, b) { return a + Math.random() * (b - a); };
      el.style.setProperty('--x', r(0, 100).toFixed(1) + '%');
      el.style.setProperty('--s', r(10, 22).toFixed(0) + 'px');
      el.style.setProperty('--d', r(11, 22).toFixed(1) + 's');
      el.style.setProperty('--delay', (-r(0, 22)).toFixed(1) + 's');
      el.style.setProperty('--sway', r(-60, 60).toFixed(0) + 'px');
      el.style.setProperty('--o', r(0.35, 0.8).toFixed(2));
      frag.appendChild(el);
    }
    layer.appendChild(frag);
  }

  /* ------------------------------------------------ V87: the menu line follows the block on screen */
  var navBox = doc.querySelector('.mbp-links');
  var line = doc.querySelector('[data-mbp-nav-line]');
  var spyLinks = Array.prototype.slice.call(doc.querySelectorAll('[data-mbp-spy]'));
  var spySections = spyLinks.map(function (a) { return doc.getElementById(a.getAttribute('data-mbp-spy')); })
    .filter(Boolean);
  var current = null;
  function placeLine() {
    if (!navBox || !line) return;
    var link = current && navBox.querySelector('[data-mbp-spy="' + current + '"]');
    if (!link || !link.offsetWidth) { line.classList.remove('is-on'); return; }
    line.style.width = link.offsetWidth - 24 + 'px';
    line.style.transform = 'translateX(' + (link.offsetLeft + 12) + 'px)';
    line.classList.add('is-on');
  }
  function setCurrent(id) {
    if (id === current) return;
    current = id;
    spyLinks.forEach(function (a) { a.classList.toggle('is-current', a.getAttribute('data-mbp-spy') === id); });
    placeLine();
  }
  if (spySections.length) {
    var spy = function () {
      // The block whose area crosses a line 35% from the top of the screen is "current".
      var mark = window.innerHeight * 0.35;
      var found = null;
      spySections.forEach(function (section) {
        var box = section.getBoundingClientRect();
        if (box.top <= mark && box.bottom > mark) found = section.id;
      });
      setCurrent(found);
    };
    var ticking = false;
    window.addEventListener('scroll', function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(function () { ticking = false; spy(); });
    }, { passive: true });
    window.addEventListener('resize', function () { placeLine(); spy(); });
    spy();
  }
  // Labels change width with the language: keep the line under the right word.
  window.addEventListener('makon:public-language', placeLine);
  if (doc.fonts && doc.fonts.ready) doc.fonts.ready.then(placeLine);

  /* ------------------------------------------------ V87: FAQ opens and closes smoothly, one at a time */
  var faqItems = Array.prototype.slice.call(doc.querySelectorAll('.mbp-faq details'));
  function animateDetails(details, open) {
    var summary = details.querySelector('summary');
    var from = details.offsetHeight;  // measured before a running animation is cancelled
    if (details._mbpAnim) details._mbpAnim.cancel();
    if (reduce || !details.animate) { details.open = open; return; }
    if (open) details.open = true;
    var to = open ? details.scrollHeight : summary.offsetHeight;
    details.classList.toggle('is-closing', !open);
    var anim = details.animate([{ height: from + 'px' }, { height: to + 'px' }],
      { duration: open ? 340 : 280, easing: 'cubic-bezier(.22, .8, .3, 1)' });
    details._mbpAnim = anim;
    details.style.overflow = 'hidden';
    anim.onfinish = function () {
      details._mbpAnim = null;
      details.classList.remove('is-closing');
      if (!open) details.open = false;
      details.style.overflow = '';
    };
    anim.oncancel = function () { details._mbpAnim = null; details.classList.remove('is-closing'); };
  }
  faqItems.forEach(function (details) {
    var summary = details.querySelector('summary');
    if (!summary) return;
    summary.addEventListener('click', function (event) {
      event.preventDefault();
      var opening = !details.open || details.classList.contains('is-closing');
      if (opening) {
        faqItems.forEach(function (other) {
          if (other !== details && other.open && !other.classList.contains('is-closing')) animateDetails(other, false);
        });
      }
      animateDetails(details, opening);
    });
  });

  /* ------------------------------------------------ reveal on scroll */
  var items = Array.prototype.slice.call(doc.querySelectorAll('[data-reveal]'));
  if (items.length) {
    if (!('IntersectionObserver' in window) || reduce) {
      items.forEach(function (n) { n.classList.add('is-in'); });
    } else {
      var fired = false;
      var io = new IntersectionObserver(function (entries) {
        fired = true;
        entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('is-in'); io.unobserve(en.target); } });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.06 });
      items.forEach(function (n) { io.observe(n); });
      // Never leave content hidden if the observer is late.
      setTimeout(function () { if (!fired) items.forEach(function (n) { n.classList.add('is-in'); }); }, 2500);
    }
  }

  apply();
  // The testimonial carousel clones slides after load: translate the copies too.
  window.addEventListener('load', function () { setTimeout(apply, 50); });
  window.MakonPublic = { apply: apply, lang: function () { return lang; }, closeMenu: function () { closeMenu(); } };
})();
