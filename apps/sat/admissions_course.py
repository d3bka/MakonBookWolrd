"""Seed content for the Admissions course.

V81: the course is SATMakon's 28 premium video lessons (folder "Lessons"). Each video
lesson carries a short written guide (from the V80 text lessons, adapted to Uzbekistan's
11-year school) and official links. Videos and PDFs are attached by
`manage.py import_admissions_media <folder>`; nothing premium is stored in this file.
"""

# V80 written guides, reused as the notes under the matching video lessons.
GUIDES_LIST = [
    {
        "slug": "how-admissions-work",
        "module": "start",
        "title": "How university admissions work",
        "summary": "What universities look at, how the main systems differ, and what a full application contains.",
        "minutes": 8,
        "steps": [
            ("Universities read a whole person, not one number",
             "In the US most selective universities use holistic review: grades, test scores, activities, essays "
             "and recommendations are read together. A strong SAT opens the door, the rest of the file decides.\n"
             "- School grades, usually for grades 9–11 (some US universities also ask for grade 8)\n"
             "- SAT or ACT, where required or helpful\n"
             "- English test (IELTS, TOEFL or Duolingo) for non-native speakers\n"
             "- Activities, awards, essays and teacher letters"),
            ("Other countries are more score-based",
             "The UK, most of Europe and much of Asia admit mainly on academic results for a specific course.\n"
             "- UK: one UCAS application, up to 5 courses, one personal statement\n"
             "- Europe: apply to each university directly, often by course, with diploma + English test\n"
             "- Asia: national universities often add their own tests or interviews"),
            ("What a complete application contains",
             "- Personal details exactly as in your international passport\n"
             "- School transcript (official, with a notarised English translation)\n"
             "- Test scores sent from the testing agency\n"
             "- Essays or a personal statement\n"
             "- 1–3 recommendation letters\n"
             "- Financial documents if you ask for aid\n"
             "- Application fee or a fee waiver"),
            ("Your first action",
             "Write down three things: the countries you would study in, the subjects you like, and how much your "
             "family can pay per year. Every later lesson uses these three answers."),
        ],
        "resources": [
            ("EducationUSA — official US study advising", "https://educationusa.state.gov", "official",
             "Free advising centres, including in Tashkent."),
            ("BigFuture by College Board", "https://bigfuture.collegeboard.org", "tool",
             "Explore colleges, majors and planning checklists."),
            ("UCAS — applying to UK universities", "https://www.ucas.com", "official", ""),
        ],
    },
    {
        "slug": "your-admissions-timeline",
        "module": "start",
        "title": "Your 18-month admissions timeline",
        "summary": "Grade by grade for an 11-year school: when to take the SAT, write essays, ask for letters and submit.",
        "minutes": 7,
        "steps": [
            ("Grade 9 – early grade 10: build the base",
             "School in Uzbekistan ends after grade 11, so you apply during grade 11.\n"
             "- Keep grades high: universities read your grades from grade 9 (sometimes 8)\n"
             "- Take a diagnostic SAT and set a target score\n"
             "- Pick 2–3 activities to go deep in instead of many shallow ones"),
            ("Grade 10: tests and research",
             "- Take the SAT for the first time (spring of grade 10 is ideal), retake in summer or early autumn\n"
             "- Take IELTS or TOEFL once your English is ready\n"
             "- Build your university list in the Universities catalogue"),
            ("Summer before grade 11: write",
             "- Draft the personal essay (Common App prompts are published every spring)\n"
             "- Ask two teachers for recommendations before school starts\n"
             "- Create your Common App / UCAS account and fill in the profile"),
            ("Grade 11: submit",
             "- Oct 15: UCAS deadline for Oxford, Cambridge and medicine\n"
             "- Nov 1 – Nov 15: Early Decision / Early Action in the US\n"
             "- Jan 1 – Jan 15: most US Regular Decision deadlines\n"
             "- Late January: main UCAS deadline\n"
             "- March – April: decisions; May 1: US reply deadline\n"
             "- June: graduation; send your final school certificate (attestat) to the university you choose"),
        ],
        "resources": [
            ("SAT dates and registration", "https://satsuite.collegeboard.org/sat/registration", "official", ""),
            ("Common App", "https://www.commonapp.org", "official", "Accounts roll over from August 1."),
            ("UCAS undergraduate", "https://www.ucas.com/undergraduate", "official", ""),
        ],
    },
    {
        "slug": "build-your-university-list",
        "module": "choose",
        "title": "Build a balanced university list",
        "summary": "Reach, match and safety schools, and how to use your SAT score to sort them.",
        "minutes": 9,
        "steps": [
            ("Three buckets",
             "- Reach: your SAT is below the middle-50% range, or the acceptance rate is under 15%\n"
             "- Match: your SAT is inside the range and the acceptance rate is reasonable\n"
             "- Safety: your SAT is above the range and you would happily go there\n"
             "Every top-20 US university is a reach for everyone, including perfect scorers."),
            ("A healthy list has 8–12 schools",
             "A common split is 3 reach, 4–5 match and 2–3 safety. Add countries with lower cost "
             "(Europe, Asia) as real options, not just backups."),
            ("Check what you can afford first",
             "Filter by tuition and by aid type before falling in love with a school. Need-blind schools with "
             "full-need aid are rare and very selective; merit scholarships are easier to plan around."),
            ("Use the MakonBook catalogue",
             "Open Universities, set your score, and filter by country, price, ranking and aid. Each university "
             "shows a Reach / Match / Safety badge for your score. Confirm every number on the official site."),
        ],
        "resources": [
            ("College Scorecard (US Department of Education)", "https://collegescorecard.ed.gov", "tool",
             "Costs, graduation rates and earnings for US colleges."),
            ("QS World University Rankings", "https://www.topuniversities.com/world-university-rankings", "guide", ""),
            ("Times Higher Education rankings", "https://www.timeshighereducation.com/world-university-rankings", "guide", ""),
        ],
    },
    {
        "slug": "countries-compared",
        "module": "choose",
        "title": "USA, UK, Europe or Asia: how they differ",
        "summary": "Degree length, cost, how you apply and what the SAT does in each region.",
        "minutes": 8,
        "steps": [
            ("United States",
             "- 4-year degree, you choose a major in year 2\n"
             "- Holistic review; SAT required again at many top schools\n"
             "- The 11-year Uzbek school certificate is accepted directly\n"
             "- Expensive, but the only place with large need-based aid for internationals"),
            ("United Kingdom",
             "- 3-year degree (4 in Scotland), you apply to one subject\n"
             "- The 11-year school certificate alone is usually not enough: you need SAT + AP exams, A-levels or IB, "
             "or a one-year Foundation programme first\n"
             "- Little financial aid for international undergraduates"),
            ("Europe",
             "- Public universities are cheap or free (Germany, Italy, Hungary) but many teach in the local language\n"
             "- Private ones (Bocconi, IE, Constructor) teach in English and use the SAT for merit scholarships\n"
             "- Many countries expect 12 years of school: with 11 years you may need a Foundation year, "
             "Studienkolleg (Germany) or a year of university at home, so check what each university asks\n"
             "- Apply university by university; deadlines run from January to May"),
            ("Asia and the Middle East",
             "- Singapore, Hong Kong and Korea teach in English and accept the SAT\n"
             "- Government scholarships (GKS, MEXT, CSC, Türkiye Bursları) can cover everything\n"
             "- Gulf universities (NYU Abu Dhabi, Khalifa) offer generous aid"),
        ],
        "resources": [
            ("DAAD — study in Germany", "https://www.daad.de/en/", "official", ""),
            ("Study in the Netherlands", "https://www.studyinnl.org", "official", ""),
            ("Campus France", "https://www.campusfrance.org/en", "official", ""),
            ("Study in Korea", "https://www.studyinkorea.go.kr", "official", ""),
            ("Study in Japan", "https://www.studyinjapan.go.jp/en/", "official", ""),
        ],
    },
    {
        "slug": "sat-strategy",
        "module": "tests",
        "title": "SAT: the score you need and when to take it",
        "summary": "Target scores, retakes, superscoring, sending scores and test-optional policies.",
        "minutes": 9,
        "steps": [
            ("Set a target from your list",
             "Take the upper end of the middle-50% range of your match schools. For top-30 US universities that is "
             "usually 1500+; for most UK, European and Asian universities 1300–1450 is enough."),
            ("Plan 2–3 sittings",
             "Most students improve on the second try. Leave 8–10 weeks between sittings to fix the mistakes from "
             "the first one (the Mistakes page in MakonBook shows them)."),
            ("Superscore and Score Choice",
             "- Many US universities superscore: they take your best Reading & Writing and best Math across dates\n"
             "- Score Choice lets you send only the dates you want, unless a school asks for all scores"),
            ("Test-optional is not test-blind",
             "Test-optional schools still read a score you send. Send it when it is at or above the school's middle "
             "50%. Test-blind schools (the University of California) ignore scores completely."),
            ("Sending scores",
             "Four free score reports if you choose the schools before test day (or up to 9 days after). "
             "Later reports cost a fee per school."),
        ],
        "resources": [
            ("The SAT — College Board", "https://satsuite.collegeboard.org/sat", "official", ""),
            ("Bluebook testing app", "https://bluebook.collegeboard.org", "tool", "Official full-length practice tests."),
            ("Khan Academy: Digital SAT", "https://www.khanacademy.org/test-prep/digital-sat", "guide", "Free official practice."),
        ],
    },
    {
        "slug": "english-tests",
        "module": "tests",
        "title": "IELTS, TOEFL and Duolingo English Test",
        "summary": "Which English test to take, the scores universities ask for, and when you can skip it.",
        "minutes": 6,
        "steps": [
            ("Which test",
             "- IELTS Academic: accepted almost everywhere, the default for the UK, Europe and Australia\n"
             "- TOEFL iBT: accepted everywhere in the US and most other places\n"
             "- Duolingo English Test: cheap and online, accepted by many US universities but fewer elsewhere"),
            ("Typical requirements",
             "- Top US universities: TOEFL 100+ or IELTS 7.0+\n"
             "- UK Russell Group: IELTS 6.5–7.5 with minimum sub-scores\n"
             "- Many European programmes: IELTS 6.0–6.5"),
            ("When you can skip it",
             "Some US universities waive the test if your SAT Reading & Writing score is high (often 650+) or if "
             "you studied in English for several years. Check each school's policy page."),
        ],
        "resources": [
            ("IELTS", "https://ielts.org", "official", ""),
            ("TOEFL iBT — ETS", "https://www.ets.org/toefl.html", "official", ""),
            ("Duolingo English Test", "https://englishtest.duolingo.com", "official", ""),
        ],
    },
    {
        "slug": "activities-and-awards",
        "module": "profile",
        "title": "Activities, awards and your profile",
        "summary": "What counts as an activity, how to describe it in 150 characters, and what makes it stand out.",
        "minutes": 8,
        "steps": [
            ("Depth beats length",
             "The Common App has room for 10 activities and 5 honors. Two or three activities with years of "
             "commitment and real results are stronger than ten clubs you joined once."),
            ("What counts",
             "- School clubs, olympiads, research, sport, music, art\n"
             "- Volunteering and community projects\n"
             "- Part-time work and family responsibilities (these count too)\n"
             "- Personal projects: an app, a blog, a small business, teaching others"),
            ("Writing each entry",
             "You have 50 characters for the position and 150 for the description. Start with a verb, give numbers "
             "and results.\n"
             "- Weak: \"Member of the debate club.\"\n"
             "- Strong: \"Led 12-person debate team; won 2 national rounds; coached 20 younger students weekly.\""),
        ],
        "resources": [
            ("Common App — applicant help center", "https://appsupport.commonapp.org", "official", ""),
            ("BigFuture: build your profile", "https://bigfuture.collegeboard.org", "guide", ""),
        ],
    },
    {
        "slug": "grades-and-school-documents",
        "module": "profile",
        "title": "Grades, transcripts and school documents",
        "summary": "Transcripts, translations, the school profile, predicted grades and who acts as your counselor.",
        "minutes": 6,
        "steps": [
            ("Transcript",
             "An official record of your grades for grades 9–11 (some universities also want grade 8), signed and "
             "stamped by your school or academic lyceum. Attach a notarised English translation."),
            ("School report and counselor",
             "In the Common App a school counselor uploads the transcript, a school profile and a counselor letter. "
             "Most schools in Uzbekistan have no counselor: ask the director, the deputy director (zavuch) or your "
             "class teacher to take this role, and explain early how the process works."),
            ("Predicted and final grades",
             "UK and many European universities give conditional offers based on predicted results. You must send "
             "your final school certificate (attestat) in summer to confirm the place."),
            ("Credential evaluation",
             "A few US universities ask for a course-by-course evaluation (for example from WES). Only order one "
             "when a school asks for it."),
        ],
        "resources": [
            ("World Education Services (WES)", "https://www.wes.org", "tool", "Only when a university asks for it."),
            ("Common App — applicant help center", "https://appsupport.commonapp.org", "official", ""),
        ],
    },
    {
        "slug": "personal-essay",
        "module": "essays",
        "title": "The personal essay",
        "summary": "Choosing a topic, structure, and the mistakes that make essays forgettable.",
        "minutes": 10,
        "steps": [
            ("What the essay is for",
             "It is the only place where admissions officers hear your voice. They want to know how you think and "
             "what you value, not a list of achievements. The Common App essay is up to 650 words."),
            ("Find a topic",
             "- List 10 small moments that changed how you see something\n"
             "- Pick the one only you could write\n"
             "- A small, specific story beats a big, general one"),
            ("Structure that works",
             "- Open inside a moment, not with a quote\n"
             "- Show what happened and what you did\n"
             "- Spend the second half on what you learned and how you changed\n"
             "- End by looking forward"),
            ("Avoid",
             "- Repeating your activities list\n"
             "- Tragedy without reflection\n"
             "- Writing what you think they want to hear\n"
             "- Letting someone else rewrite your voice (AI included)"),
            ("Draft, rest, rewrite",
             "Plan for 5–8 drafts over 2 months. Ask one teacher and one friend who knows you to read it."),
        ],
        "resources": [
            ("Common App essay prompts", "https://www.commonapp.org/blog", "official", "Prompts are announced each year."),
            ("UCAS personal statement guide", "https://www.ucas.com/undergraduate", "official",
             "From the 2026 entry the UK statement uses three questions."),
        ],
    },
    {
        "slug": "supplemental-essays",
        "module": "essays",
        "title": "Supplemental essays and \"Why us?\"",
        "summary": "School-specific essays: how to research them and reuse work without sounding generic.",
        "minutes": 7,
        "steps": [
            ("What supplements ask",
             "- Why this university?\n"
             "- Why this major?\n"
             "- Community, diversity or challenge essays\n"
             "- Short answers (favourite book, a word that describes you)"),
            ("Research before you write",
             "Name specific courses, professors, labs, programs or student groups, and connect each to something you "
             "have already done. If a sentence would work for another university, rewrite it."),
            ("Reuse wisely",
             "Many prompts overlap. Keep a document with your best paragraphs and adapt them, but always rewrite "
             "the \"why us\" part from scratch."),
        ],
        "resources": [
            ("Common App", "https://www.commonapp.org", "official", "Supplements appear in each college's section."),
        ],
    },
    {
        "slug": "recommendation-letters",
        "module": "essays",
        "title": "Recommendation letters",
        "summary": "Who to ask, when to ask, and what to give your teachers so their letters are specific.",
        "minutes": 5,
        "steps": [
            ("Who",
             "Two teachers of core subjects from grade 10 or 11 who know you well, ideally one in sciences or math "
             "and one in humanities, plus the person acting as your counselor (director, zavuch or class teacher)."),
            ("When",
             "Ask at least two months before the first deadline. Teachers write many letters in October."),
            ("Help them",
             "- Give a one-page brag sheet: your goals, projects, moments from their class\n"
             "- A teacher may write in Uzbek or Russian; the school then attaches an English translation\n"
             "- Thank them, and tell them where you got in"),
        ],
        "resources": [
            ("Common App — recommender help", "https://appsupport.commonapp.org", "official", ""),
        ],
    },
    {
        "slug": "common-app-step-by-step",
        "module": "apply",
        "title": "The Common App, step by step",
        "summary": "Every section of the Common App and how to fill it in without mistakes.",
        "minutes": 10,
        "steps": [
            ("Create the account",
             "Use a personal email you will keep for years. Your name must match the Latin spelling in your "
             "international passport exactly."),
            ("Profile, family, education",
             "- Profile: contact details, citizenship, language\n"
             "- Family: parents' education and occupation\n"
             "- Education: school, counselor contact (director or zavuch), courses and grades for grades 9–11"),
            ("Testing, activities, writing",
             "- Testing: self-report SAT and English scores\n"
             "- Activities: up to 10, see the Activities lesson\n"
             "- Writing: the personal essay and an optional additional-information section"),
            ("College section",
             "Add each university: answer its questions, upload supplements, choose a plan (ED, EA, RD) and invite "
             "recommenders."),
            ("Before you press Submit",
             "- Read the PDF preview of the whole application\n"
             "- Pay the fee or request a fee waiver\n"
             "- Send official test scores from College Board\n"
             "- Check every university's portal a few days later for missing documents"),
        ],
        "resources": [
            ("Common App", "https://apply.commonapp.org", "official", ""),
            ("Common App — applicant help center", "https://appsupport.commonapp.org", "official", ""),
            ("Send SAT scores", "https://satsuite.collegeboard.org/sat/scores/sending-scores", "official", ""),
        ],
    },
    {
        "slug": "applying-through-ucas",
        "module": "apply",
        "title": "Applying to the UK through UCAS",
        "summary": "Five choices, one personal statement, one reference, and the deadlines that matter.",
        "minutes": 7,
        "steps": [
            ("Five choices, one subject",
             "You can apply to up to five courses. Every university sees the same personal statement, so pick "
             "courses in the same subject area."),
            ("Requirements for SAT students",
             "The Uzbek school certificate on its own is usually not enough. Most UK universities accept the SAT "
             "together with AP exams (often three APs with scores of 4–5), A-levels or IB, or a Foundation year. "
             "Check the \"international qualifications\" page of each university for Uzbekistan."),
            ("Deadlines",
             "- October 15: Oxford, Cambridge, medicine, dentistry, veterinary science\n"
             "- Late January: equal-consideration deadline for most other courses"),
            ("Offers",
             "Offers are usually conditional on final results. You choose one firm and one insurance offer."),
        ],
        "resources": [
            ("UCAS", "https://www.ucas.com", "official", ""),
            ("UCAS for international students", "https://www.ucas.com/international", "official", ""),
        ],
    },
    {
        "slug": "financial-aid",
        "module": "money",
        "title": "Financial aid: need-blind, need-aware and the CSS Profile",
        "summary": "How need-based aid works for international students and which forms you will fill in.",
        "minutes": 9,
        "steps": [
            ("The vocabulary",
             "- Cost of attendance: tuition + housing + food + insurance + travel\n"
             "- Need-blind: your ability to pay does not affect admission\n"
             "- Need-aware: it can, so asking for aid makes admission harder\n"
             "- Meets full need: whatever they calculate your family cannot pay, they cover"),
            ("The forms",
             "- CSS Profile: used by most private US universities, filled online by College Board\n"
             "- Some schools use their own form (ISFAA) and ask for tax or salary documents\n"
             "- Use the school's Net Price Calculator before you apply"),
            ("Be honest and consistent",
             "Income, savings and property must match the documents you upload. Universities compare them.\n"
             "- In Uzbekistan this usually means income certificates (spravka) from your parents' employers and "
             "bank statements, with English translations\n"
             "- If a parent is self-employed or paid informally, explain it in a short signed letter"),
        ],
        "resources": [
            ("CSS Profile", "https://cssprofile.collegeboard.org", "official", ""),
            ("Net Price Calculator Center", "https://collegecost.ed.gov/net-price", "tool", ""),
            ("EducationUSA: financial aid", "https://educationusa.state.gov", "official", ""),
        ],
    },
    {
        "slug": "scholarships",
        "module": "money",
        "title": "Scholarships for international students",
        "summary": "University merit awards and government scholarships that cover tuition and living costs.",
        "minutes": 8,
        "steps": [
            ("University merit scholarships",
             "Many universities give automatic or competitive awards for a high SAT and strong grades, for example "
             "in the US (USC, Vanderbilt, ASU), Italy (Bocconi), Turkey (Koç, Bilkent) and Germany (Constructor). "
             "Some have early scholarship deadlines in December."),
            ("Government scholarships",
             "- Stipendium Hungaricum (Hungary)\n"
             "- Global Korea Scholarship (South Korea)\n"
             "- MEXT (Japan)\n"
             "- Chinese Government Scholarship\n"
             "- Türkiye Bursları (Turkey)"),
            ("From Uzbekistan",
             "El-Yurt Umidi Foundation supports students admitted to leading foreign universities. Check the "
             "current programs and deadlines on its site."),
        ],
        "resources": [
            ("Stipendium Hungaricum", "https://stipendiumhungaricum.hu", "official", ""),
            ("Study in Korea — GKS", "https://www.studyinkorea.go.kr", "official", ""),
            ("Study in Japan — MEXT", "https://www.studyinjapan.go.jp/en/", "official", ""),
            ("Campus China — CSC scholarship", "https://www.campuschina.org", "official", ""),
            ("Türkiye Bursları", "https://www.turkiyeburslari.gov.tr", "official", ""),
            ("El-Yurt Umidi Foundation", "https://eyuf.uz", "official", ""),
        ],
    },
    {
        "slug": "decisions-and-visa",
        "module": "after",
        "title": "Decisions, waitlists and the student visa",
        "summary": "What to do after you submit: interviews, decisions, deposits and the visa.",
        "minutes": 7,
        "steps": [
            ("After you submit",
             "Check each portal for missing documents, prepare for interviews (alumni or online), and send "
             "mid-year grades when asked."),
            ("Decisions",
             "- Admitted: compare aid packages; you can ask for a review if your situation changed\n"
             "- Waitlisted: send one short letter of continued interest with new achievements\n"
             "- Deferred (early round): you are moved to the regular round"),
            ("Confirm one place",
             "In the US pay one enrollment deposit by May 1. In the UK accept a firm and an insurance offer."),
            ("The visa",
             "- US: the university sends the I-20, you pay the SEVIS fee and book the F-1 interview at the "
             "US Embassy in Tashkent\n"
             "- UK: the university gives you a CAS number; you apply for the Student visa online and give "
             "biometrics at the visa centre in Tashkent\n"
             "- Prepare bank statements that match the amount on your documents"),
        ],
        "resources": [
            ("US student visa — travel.state.gov", "https://travel.state.gov/content/travel/en/us-visas/study/student-visa.html", "official", ""),
            ("SEVIS I-901 fee", "https://www.fmjfee.com", "official", ""),
            ("UK Student visa — GOV.UK", "https://www.gov.uk/student-visa", "official", ""),
        ],
    },
]
GUIDES = {guide["slug"]: guide for guide in GUIDES_LIST}

# The V80 text-only lessons; replaced by the video course (migration 0073).
V80_LESSON_SLUGS = [guide["slug"] for guide in GUIDES_LIST]


def _video(number, slug, module, title, summary, minutes, guides=(), links=()):
    steps, resources = [], list(links)
    for name in guides:
        steps += GUIDES[name]["steps"]
        seen = {item[1] for item in resources}
        resources += [item for item in GUIDES[name]["resources"] if item[1] not in seen]
    return {"number": number, "slug": slug, "module": module, "title": title, "summary": summary,
            "minutes": minutes, "steps": steps, "resources": resources}


# order == the number in the video file name ("Lesson 7 - Gap Year Essay.mp4" -> 7).
LESSONS = [
    _video(1, "introduction", "start", "Introduction",
           "How the course works and the road from SAT score to an admission letter.", 24,
           ["how-admissions-work", "your-admissions-timeline"]),
    _video(2, "common-app", "start", "Common App",
           "The Common App platform: the account, its sections and how universities receive it.", 20,
           ["common-app-step-by-step"]),
    _video(3, "top-universities", "choose", "Top universities",
           "The leading universities, what makes them different and what they look for.", 31,
           ["countries-compared"]),
    _video(4, "reach-match-safety", "choose", "Reach, match and safety",
           "Sorting your list into reach, match and safety schools.", 21, ["build-your-university-list"]),
    _video(5, "numbers", "choose", "Numbers",
           "Acceptance rates, SAT ranges, English scores and the other numbers behind a decision.", 16,
           ["sat-strategy", "english-tests"]),
    _video(6, "family-and-education", "profile", "Family and education",
           "Filling in the Family and Education sections without mistakes.", 15,
           links=[("Common App — applicant help center", "https://appsupport.commonapp.org", "official", "")]),
    _video(7, "gap-year-essay", "essays", "Gap year essay",
           "Explaining a gap year in your application.", 15,
           links=[("Common App — applicant help center", "https://appsupport.commonapp.org", "official", "")]),
    _video(8, "activity-types", "profile", "Activity types",
           "Which activities count and how universities read them.", 18, ["activities-and-awards"]),
    _video(9, "leadership-skills", "profile", "Leadership skills",
           "Showing leadership through what you have actually done.", 14,
           links=[("Common App — applicant help center", "https://appsupport.commonapp.org", "official", "")]),
    _video(10, "successful-description", "profile", "Successful description",
           "Writing activity descriptions that stand out.", 18,
           links=[("Common App — applicant help center", "https://appsupport.commonapp.org", "official", "")]),
    _video(11, "self-reflection-essay", "essays", "Self-reflection essay",
           "Writing about yourself honestly and with insight.", 11,
           links=[("Common App essay prompts", "https://www.commonapp.org/blog", "official", "")]),
    _video(12, "personal-statement-essay", "essays", "Personal statement essay",
           "Choosing a topic and building the Common App personal statement.", 20, ["personal-essay"]),
    _video(13, "examples-of-essays", "essays", "Examples of essays",
           "Successful essays, read and analysed.", 18,
           links=[("Common App essay prompts", "https://www.commonapp.org/blog", "official", "")]),
    _video(14, "supplemental-essays", "essays", "Supplemental essays",
           "University-specific essays, including \"Why us?\"", 24, ["supplemental-essays"]),
    _video(15, "activity-essay", "essays", "Activity essay",
           "Turning one activity into a strong short essay.", 20,
           links=[("Common App — applicant help center", "https://appsupport.commonapp.org", "official", "")]),
    _video(16, "merit-scholarship", "money", "Merit scholarships",
           "Universities that reward strong students with merit scholarships, and how to apply.", 18,
           ["scholarships"]),
    _video(17, "css-profile", "money", "CSS Profile",
           "Filling in the CSS Profile for need-based financial aid.", 48, ["financial-aid"]),
    _video(18, "school-profile", "apply", "School profile",
           "The school profile, transcript and the documents your school sends.", 21,
           ["grades-and-school-documents"]),
    _video(19, "recommendation-letter", "apply", "Recommendation letters",
           "Who writes your letters and how to help them write strong ones.", 8, ["recommendation-letters"]),
    _video(20, "additional-section", "apply", "Additional information section",
           "What belongs in the Additional Information section and what does not.", 11,
           links=[("Common App — applicant help center", "https://appsupport.commonapp.org", "official", "")]),
    _video(21, "united-kingdom", "countries", "United Kingdom",
           "Studying in the UK: requirements for Uzbek students and the UCAS application.", 23,
           ["applying-through-ucas"]),
    _video(22, "ucas-personal-statement", "countries", "UCAS personal statement",
           "Writing the UCAS personal statement.", 28,
           links=[("UCAS undergraduate", "https://www.ucas.com/undergraduate", "official", "")]),
    _video(23, "turkey", "countries", "Turkey",
           "Studying in Turkey: universities, applications and scholarships.", 21,
           links=[("Türkiye Bursları", "https://www.turkiyeburslari.gov.tr", "official", "Government scholarship.")]),
    _video(24, "australia", "countries", "Australia",
           "Studying in Australia: universities and how to apply.", 22,
           links=[("Study Australia", "https://www.studyaustralia.gov.au", "official", ""),
                  ("Australian Student visa", "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/student-500", "official", "")]),
    _video(25, "post-acceptance-process", "after", "After you are admitted",
           "Decisions, deposits, documents and the student visa.", 10, ["decisions-and-visa"]),
    _video(26, "asia", "countries", "Asia",
           "Studying in Asia: universities and scholarships.", 18,
           links=[("Study in Korea — GKS", "https://www.studyinkorea.go.kr", "official", ""),
                  ("Study in Japan — MEXT", "https://www.studyinjapan.go.jp/en/", "official", ""),
                  ("Campus China — CSC scholarship", "https://www.campuschina.org", "official", "")]),
    _video(27, "college-interview", "after", "College interview",
           "Preparing for admissions interviews.", 21,
           links=[("EducationUSA — official US study advising", "https://educationusa.state.gov", "official", "")]),
    _video(28, "el-yurt-umidi", "money", "El-Yurt Umidi Foundation",
           "Support from Uzbekistan's El-Yurt Umidi Foundation for studying abroad.", 13,
           links=[("El-Yurt Umidi Foundation", "https://eyuf.uz", "official", "Programs and deadlines.")]),
]

# Premium PDFs from the Lessons folder: shown page by page with the viewer's watermark.
DOCUMENTS = [
    {"slug": "university-list", "title": "University list", "source": "University list -1-2.pdf",
     "description": "SATMakon university list.", "lessons": [3, 4]},
    {"slug": "why-us", "title": "Why US", "source": "Why US.pdf",
     "description": "SATMakon guide.", "lessons": [14]},
    {"slug": "activities-lists", "title": "15 successful activities lists",
     "source": "15 Successful Activities Lists eBook.pdf",
     "description": "Activities lists of admitted students.", "lessons": [8, 10]},
    {"slug": "harvard-essays", "title": "50 successful Harvard application essays",
     "source": "50_Successful_Harvard_Application_Essays_4th_Edition_With_Analysis.pdf",
     "description": "Essays with analysis.", "lessons": [13]},
    {"slug": "full-scholarship-schools", "title": "Schools that offer full scholarships",
     "source": "A-Schools-That-Offer-Full-Scholarships-2019-01-07-2021-HM.pdf",
     "description": "Universities with full scholarships for international students.", "lessons": [16]},
    {"slug": "merit-scholarships", "title": "Merit scholarships", "source": "Merit scholarships.pdf",
     "description": "Merit scholarship list.", "lessons": [16]},
    {"slug": "scholarship-sizes", "title": "Size of US university scholarships",
     "source": "Size of US Universities schoolarships.pdf",
     "description": "How large scholarships are at US universities.", "lessons": [16, 17]},
]


def load_admissions_course(Lesson, Step, Resource):
    """Create lessons that do not exist yet (by slug), with their steps and resources.

    Existing lessons are left alone so admin edits survive re-runs.
    Returns the number of lessons created.
    """
    created = 0
    for data in LESSONS:
        if Lesson.objects.filter(slug=data["slug"]).exists():
            continue
        lesson = Lesson.objects.create(
            order=data["number"], slug=data["slug"], module=data["module"], title=data["title"],
            summary=data["summary"], minutes=data["minutes"],
        )
        for step_order, (title, body) in enumerate(data["steps"], start=1):
            Step.objects.create(lesson=lesson, order=step_order, title=title, body=body)
        for res_order, (title, url, kind, note) in enumerate(data["resources"], start=1):
            Resource.objects.create(lesson=lesson, order=res_order, title=title, url=url, kind=kind, note=note)
        created += 1
    return created


def load_admissions_documents(Document, Lesson):
    """Create the premium file records (no pages yet: the import command renders them)."""
    created = 0
    for order, data in enumerate(DOCUMENTS, start=1):
        document, made = Document.objects.get_or_create(slug=data["slug"], defaults={
            "title": data["title"], "description": data["description"], "order": order,
            "source_name": data["source"],
        })
        if made:
            slugs = [lesson["slug"] for lesson in LESSONS if lesson["number"] in data["lessons"]]
            document.lessons.set(Lesson.objects.filter(slug__in=slugs))
            created += 1
    return created
