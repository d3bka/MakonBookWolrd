"""V80 seed data for the Universities catalogue.

Public figures for the 2024–25 admissions cycle, rounded. They change every year:
the page tells students to confirm on the university's own site, and admins can edit
every row in the Django admin (sat › Universities).

Columns:
name, country, city, region, type, QS band, acceptance %, SAT low, SAT high, SAT kind,
test policy, IELTS min, TOEFL min, intl tuition USD/yr, aid, platform, deadlines, website, notes
  SAT kind: middle50 = middle 50% of admitted students, minimum = typical requirement, none = not used
"""

NA, EU, AS, ME, OC = "north_america", "europe", "asia", "middle_east", "oceania"

UNIVERSITIES = [
    # ---------------------------------------------------------------- USA: most selective
    ("Massachusetts Institute of Technology (MIT)", "USA", "Cambridge, MA", NA, "private", "top10", 4.5, 1520, 1580, "middle50", "required", 7.0, 90, 62000, "need_blind", "direct", "EA Nov 1 · RD Jan 6", "https://mitadmissions.org", "Need-blind for international students; meets full demonstrated need."),
    ("Harvard University", "USA", "Cambridge, MA", NA, "private", "top10", 3.6, 1500, 1580, "middle50", "required", None, None, 57000, "need_blind", "common_app", "REA Nov 1 · RD Jan 1", "https://college.harvard.edu/admissions", "Need-blind for all applicants; families under about $85k pay nothing."),
    ("Stanford University", "USA", "Stanford, CA", NA, "private", "top10", 3.9, 1510, 1570, "middle50", "required", None, None, 65000, "need_aware", "common_app", "REA Nov 1 · RD Jan 5", "https://admission.stanford.edu", "Need-aware for international applicants, then meets full need."),
    ("Yale University", "USA", "New Haven, CT", NA, "private", "top50", 3.7, 1500, 1580, "middle50", "required", None, None, 67000, "need_blind", "common_app", "SCEA Nov 1 · RD Jan 2", "https://admissions.yale.edu", "Test-flexible: SAT, ACT, AP or IB scores accepted."),
    ("Princeton University", "USA", "Princeton, NJ", NA, "private", "top50", 4.5, 1500, 1580, "middle50", "required", None, None, 62000, "need_blind", "common_app", "SCEA Nov 1 · RD Jan 1", "https://admission.princeton.edu", "No loans in aid packages."),
    ("Columbia University", "USA", "New York, NY", NA, "private", "top50", 3.9, 1500, 1570, "middle50", "optional", None, None, 69000, "need_aware", "common_app", "ED Nov 1 · RD Jan 1", "https://undergrad.admissions.columbia.edu", ""),
    ("University of Pennsylvania", "USA", "Philadelphia, PA", NA, "private", "top50", 5.4, 1500, 1570, "middle50", "required", None, None, 69000, "need_aware", "common_app", "ED Nov 1 · RD Jan 5", "https://admissions.upenn.edu", ""),
    ("Brown University", "USA", "Providence, RI", NA, "private", "top100", 5.2, 1510, 1570, "middle50", "required", None, None, 69000, "need_blind", "common_app", "ED Nov 1 · RD Jan 3", "https://admission.brown.edu", "Need-blind for international applicants from the fall 2025 entry."),
    ("Dartmouth College", "USA", "Hanover, NH", NA, "private", "top500", 6.2, 1500, 1580, "middle50", "required", None, None, 67000, "need_blind", "common_app", "ED Nov 1 · RD Jan 3", "https://admissions.dartmouth.edu", "Need-blind for international students."),
    ("Cornell University", "USA", "Ithaca, NY", NA, "private", "top50", 8.4, 1480, 1560, "middle50", "required", 7.0, 100, 70000, "need_aware", "common_app", "ED Nov 1 · RD Jan 2", "https://admissions.cornell.edu", ""),
    ("California Institute of Technology (Caltech)", "USA", "Pasadena, CA", NA, "private", "top10", 2.6, 1530, 1580, "middle50", "required", None, None, 66000, "need_aware", "common_app", "REA Nov 1 · RD Jan 3", "https://www.admissions.caltech.edu", ""),
    ("University of Chicago", "USA", "Chicago, IL", NA, "private", "top50", 4.5, 1510, 1560, "middle50", "optional", None, None, 70000, "need_aware", "common_app", "ED/EA Nov 1 · RD Jan 6", "https://collegeadmissions.uchicago.edu", ""),
    ("Johns Hopkins University", "USA", "Baltimore, MD", NA, "private", "top50", 6.0, 1530, 1560, "middle50", "required", None, None, 66000, "need_aware", "common_app", "ED Nov 1 · RD Jan 2", "https://apply.jhu.edu", ""),
    ("Duke University", "USA", "Durham, NC", NA, "private", "top50", 5.1, 1510, 1570, "middle50", "optional", None, None, 67000, "need_aware", "common_app", "ED Nov 1 · RD Jan 2", "https://admissions.duke.edu", ""),
    ("Northwestern University", "USA", "Evanston, IL", NA, "private", "top50", 7.0, 1510, 1560, "middle50", "optional", None, None, 66000, "need_aware", "common_app", "ED Nov 1 · RD Jan 2", "https://admissions.northwestern.edu", ""),
    ("Vanderbilt University", "USA", "Nashville, TN", NA, "private", "top500", 5.6, 1500, 1570, "middle50", "optional", None, None, 65000, "need_aware", "common_app", "ED Nov 1 · RD Jan 1", "https://admissions.vanderbilt.edu", "Merit: Ingram, Cornelius Vanderbilt and Chancellor's scholarships."),
    ("Rice University", "USA", "Houston, TX", NA, "private", "top200", 7.9, 1500, 1570, "middle50", "optional", None, None, 62000, "need_aware", "common_app", "ED Nov 1 · RD Jan 4", "https://admission.rice.edu", ""),
    ("University of Notre Dame", "USA", "Notre Dame, IN", NA, "private", "top500", 11.0, 1460, 1550, "middle50", "optional", None, None, 66000, "need_blind", "common_app", "REA Nov 1 · RD Jan 1", "https://admissions.nd.edu", "Need-blind for international students from the 2025 entry."),
    ("Georgetown University", "USA", "Washington, DC", NA, "private", "top500", 13.0, 1410, 1560, "middle50", "required", None, None, 67000, "limited", "direct", "EA Nov 1 · RD Jan 10", "https://uadmissions.georgetown.edu", "Uses its own application, not Common App."),
    ("Washington University in St. Louis", "USA", "St. Louis, MO", NA, "private", "top500", 12.0, 1500, 1570, "middle50", "optional", None, None, 66000, "need_aware", "common_app", "ED Nov 1 · RD Jan 2", "https://admissions.wustl.edu", ""),
    ("Emory University", "USA", "Atlanta, GA", NA, "private", "top500", 11.0, 1470, 1540, "middle50", "optional", None, None, 63000, "need_aware", "common_app", "ED Nov 1 · RD Jan 1", "https://apply.emory.edu", ""),
    ("Carnegie Mellon University", "USA", "Pittsburgh, PA", NA, "private", "top100", 11.0, 1510, 1560, "middle50", "required", 7.5, 102, 66000, "limited", "common_app", "ED Nov 1 · RD Jan 3", "https://admission.enrollment.cmu.edu", ""),
    ("New York University", "USA", "New York, NY", NA, "private", "top50", 9.0, 1470, 1570, "middle50", "optional", 7.5, 100, 62000, "limited", "common_app", "ED Nov 1 · RD Jan 5", "https://www.nyu.edu/admissions", ""),
    ("University of Southern California", "USA", "Los Angeles, CA", NA, "private", "top200", 10.0, 1450, 1540, "middle50", "optional", 7.0, 100, 70000, "merit", "common_app", "EA Nov 1 · RD Jan 15", "https://admission.usc.edu", "Merit: Trustee and Presidential scholarships (apply by Dec 1)."),
    ("Tufts University", "USA", "Medford, MA", NA, "private", "top500", 10.0, 1470, 1550, "middle50", "optional", 7.0, 100, 69000, "need_aware", "common_app", "ED Nov 1 · RD Jan 4", "https://admissions.tufts.edu", ""),
    ("Boston University", "USA", "Boston, MA", NA, "private", "top200", 11.0, 1440, 1540, "middle50", "optional", 7.0, 100, 67000, "limited", "common_app", "ED Nov 1 · RD Jan 4", "https://www.bu.edu/admissions", ""),
    ("Boston College", "USA", "Chestnut Hill, MA", NA, "private", "top500", 16.0, 1440, 1530, "middle50", "required", 7.0, 100, 69000, "limited", "common_app", "ED Nov 1 · RD Jan 2", "https://www.bc.edu/admission", ""),
    ("Northeastern University", "USA", "Boston, MA", NA, "private", "top500", 5.6, 1450, 1550, "middle50", "optional", 7.0, 100, 64000, "merit", "common_app", "ED/EA Nov 1 · RD Jan 1", "https://admissions.northeastern.edu", "Co-op program: paid work semesters."),
    ("University of Rochester", "USA", "Rochester, NY", NA, "private", "top500", 36.0, 1370, 1530, "middle50", "optional", 6.5, 90, 66000, "merit", "common_app", "ED Nov 1 · RD Jan 5", "https://www.rochester.edu/admissions", ""),
    ("Case Western Reserve University", "USA", "Cleveland, OH", NA, "private", "top500", 30.0, 1420, 1530, "middle50", "optional", 7.0, 90, 66000, "merit", "common_app", "ED/EA Nov 1 · RD Jan 15", "https://case.edu/admission", ""),
    ("Tulane University", "USA", "New Orleans, LA", NA, "private", "other", 13.0, 1430, 1520, "middle50", "optional", 6.5, 90, 68000, "merit", "common_app", "ED/EA Nov 1 · RD Jan 15", "https://admission.tulane.edu", ""),
    ("Wake Forest University", "USA", "Winston-Salem, NC", NA, "private", "other", 22.0, 1410, 1510, "middle50", "optional", 7.0, 100, 67000, "limited", "common_app", "ED Nov 15 · RD Jan 1", "https://admissions.wfu.edu", ""),
    ("Lehigh University", "USA", "Bethlehem, PA", NA, "private", "other", 29.0, 1360, 1490, "middle50", "optional", 7.0, 90, 64000, "limited", "common_app", "ED Nov 1 · RD Jan 1", "https://admissions.lehigh.edu", ""),
    ("Brandeis University", "USA", "Waltham, MA", NA, "private", "other", 39.0, 1350, 1520, "middle50", "optional", 7.0, 100, 66000, "merit", "common_app", "ED Nov 1 · RD Jan 1", "https://www.brandeis.edu/admissions", "Wien International Scholarship for international students."),
    ("Rensselaer Polytechnic Institute", "USA", "Troy, NY", NA, "private", "top500", 57.0, 1340, 1520, "middle50", "optional", 6.5, 88, 63000, "merit", "common_app", "ED Nov 1 · RD Jan 15", "https://admissions.rpi.edu", ""),
    ("Villanova University", "USA", "Villanova, PA", NA, "private", "other", 23.0, 1390, 1500, "middle50", "optional", 7.0, 100, 66000, "limited", "common_app", "ED/EA Nov 1 · RD Jan 15", "https://www1.villanova.edu/university/undergraduate-admission.html", ""),
    ("George Washington University", "USA", "Washington, DC", NA, "private", "top500", 44.0, 1350, 1500, "middle50", "optional", 7.0, 100, 66000, "merit", "common_app", "ED Nov 1 · RD Jan 5", "https://undergraduate.admissions.gwu.edu", ""),
    ("American University", "USA", "Washington, DC", NA, "private", "other", 47.0, 1250, 1410, "middle50", "optional", 6.5, 90, 58000, "merit", "common_app", "ED/EA Nov 1 · RD Jan 15", "https://www.american.edu/admissions", ""),
    ("Syracuse University", "USA", "Syracuse, NY", NA, "private", "other", 42.0, 1250, 1410, "middle50", "optional", 6.5, 90, 63000, "merit", "common_app", "ED Nov 15 · RD Jan 5", "https://admissions.syr.edu", ""),
    ("Fordham University", "USA", "New York, NY", NA, "private", "other", 54.0, 1310, 1460, "middle50", "optional", 6.5, 90, 62000, "merit", "common_app", "ED/EA Nov 1 · RD Jan 1", "https://www.fordham.edu/admissions", ""),
    ("University of Miami", "USA", "Coral Gables, FL", NA, "private", "top500", 19.0, 1350, 1460, "middle50", "optional", 6.5, 80, 62000, "merit", "common_app", "ED/EA Nov 1 · RD Jan 1", "https://admissions.miami.edu", ""),
    ("Drexel University", "USA", "Philadelphia, PA", NA, "private", "other", 83.0, 1180, 1390, "middle50", "optional", 6.5, 79, 63000, "merit", "common_app", "ED Nov 1 · RD Jan 15", "https://drexel.edu/undergrad", "Co-op program."),
    # ---------------------------------------------------------------- USA: liberal arts colleges (not in QS world rankings)
    ("Williams College", "USA", "Williamstown, MA", NA, "private", "other", 8.0, 1490, 1560, "middle50", "optional", None, None, 66000, "need_blind", "common_app", "ED Nov 15 · RD Jan 8", "https://admission.williams.edu", "Liberal arts college; meets full need with no loans."),
    ("Amherst College", "USA", "Amherst, MA", NA, "private", "other", 9.0, 1480, 1560, "middle50", "optional", None, None, 68000, "need_blind", "common_app", "ED Nov 1 · RD Jan 3", "https://www.amherst.edu/admission", "Liberal arts college; need-blind for international students."),
    ("Swarthmore College", "USA", "Swarthmore, PA", NA, "private", "other", 7.0, 1480, 1560, "middle50", "optional", None, None, 64000, "need_aware", "common_app", "ED Nov 15 · RD Jan 4", "https://www.swarthmore.edu/admissions-aid", "Liberal arts college."),
    ("Pomona College", "USA", "Claremont, CA", NA, "private", "other", 7.0, 1470, 1550, "middle50", "optional", None, None, 63000, "need_aware", "common_app", "ED Nov 15 · RD Jan 8", "https://www.pomona.edu/admissions", "Liberal arts college."),
    ("Wellesley College", "USA", "Wellesley, MA", NA, "private", "other", 14.0, 1440, 1550, "middle50", "optional", None, None, 66000, "need_aware", "common_app", "ED Nov 1 · RD Jan 8", "https://www.wellesley.edu/admission", "Women's liberal arts college."),
    ("Bowdoin College", "USA", "Brunswick, ME", NA, "private", "other", 7.0, 1460, 1540, "middle50", "optional", None, None, 66000, "need_aware", "common_app", "ED Nov 15 · RD Jan 5", "https://www.bowdoin.edu/admissions", "Liberal arts college."),
    ("Middlebury College", "USA", "Middlebury, VT", NA, "private", "other", 11.0, 1440, 1540, "middle50", "optional", None, None, 66000, "need_aware", "common_app", "ED Nov 1 · RD Jan 3", "https://www.middlebury.edu/admissions", "Liberal arts college."),
    ("Grinnell College", "USA", "Grinnell, IA", NA, "private", "other", 11.0, 1380, 1530, "middle50", "optional", None, None, 64000, "need_aware", "common_app", "ED Nov 15 · RD Jan 15", "https://www.grinnell.edu/admission", "Liberal arts college; generous aid for internationals."),
    ("Colby College", "USA", "Waterville, ME", NA, "private", "other", 7.0, 1450, 1530, "middle50", "optional", None, None, 68000, "need_aware", "common_app", "ED Nov 15 · RD Jan 2", "https://www.colby.edu/admission", "Liberal arts college."),
    ("Carleton College", "USA", "Northfield, MN", NA, "private", "other", 18.0, 1420, 1550, "middle50", "optional", None, None, 66000, "need_aware", "common_app", "ED Nov 15 · RD Jan 15", "https://www.carleton.edu/admissions", "Liberal arts college."),
    ("Davidson College", "USA", "Davidson, NC", NA, "private", "other", 13.0, 1400, 1520, "middle50", "optional", None, None, 64000, "need_aware", "common_app", "ED Nov 15 · RD Jan 5", "https://www.davidson.edu/admission-and-financial-aid", "Liberal arts college."),
    ("Hamilton College", "USA", "Clinton, NY", NA, "private", "other", 12.0, 1450, 1540, "middle50", "optional", None, None, 66000, "need_aware", "common_app", "ED Nov 15 · RD Jan 1", "https://www.hamilton.edu/admission", "Liberal arts college."),
    ("Vassar College", "USA", "Poughkeepsie, NY", NA, "private", "other", 18.0, 1440, 1530, "middle50", "optional", None, None, 68000, "need_aware", "common_app", "ED Nov 15 · RD Jan 1", "https://www.vassar.edu/admission", "Liberal arts college."),
    ("Colgate University", "USA", "Hamilton, NY", NA, "private", "other", 13.0, 1410, 1520, "middle50", "optional", None, None, 68000, "need_aware", "common_app", "ED Nov 15 · RD Jan 15", "https://www.colgate.edu/admission-financial-aid", "Liberal arts college."),
    ("Haverford College", "USA", "Haverford, PA", NA, "private", "other", 13.0, 1440, 1540, "middle50", "optional", None, None, 68000, "need_aware", "common_app", "ED Nov 15 · RD Jan 5", "https://www.haverford.edu/admission", "Liberal arts college."),
    ("Barnard College", "USA", "New York, NY", NA, "private", "other", 8.0, 1450, 1540, "middle50", "optional", None, None, 66000, "limited", "common_app", "ED Nov 1 · RD Jan 1", "https://barnard.edu/admissions", "Women's college of Columbia University."),
    ("Bates College", "USA", "Lewiston, ME", NA, "private", "other", 13.0, 1400, 1520, "middle50", "optional", None, None, 66000, "need_aware", "common_app", "ED Nov 15 · RD Jan 10", "https://www.bates.edu/admission", "Liberal arts college."),
    ("Macalester College", "USA", "Saint Paul, MN", NA, "private", "other", 28.0, 1340, 1500, "middle50", "optional", None, None, 64000, "need_aware", "common_app", "ED Nov 1 · RD Jan 15", "https://www.macalester.edu/admissions", "Liberal arts college with many international students."),
    ("Smith College", "USA", "Northampton, MA", NA, "private", "other", 22.0, 1390, 1530, "middle50", "optional", None, None, 63000, "need_aware", "common_app", "ED Nov 15 · RD Jan 15", "https://www.smith.edu/admission-aid", "Women's liberal arts college."),
    ("Bryn Mawr College", "USA", "Bryn Mawr, PA", NA, "private", "other", 33.0, 1340, 1500, "middle50", "optional", None, None, 64000, "need_aware", "common_app", "ED Nov 15 · RD Jan 15", "https://www.brynmawr.edu/admissions-aid", "Women's liberal arts college."),
    ("Oberlin College", "USA", "Oberlin, OH", NA, "private", "other", 33.0, 1310, 1490, "middle50", "optional", None, None, 66000, "need_aware", "common_app", "ED Nov 15 · RD Jan 15", "https://www.oberlin.edu/admissions-and-aid", "Liberal arts college and conservatory."),
    ("Minerva University", "USA", "San Francisco, CA", NA, "private", "other", 2.0, None, None, "none", "blind", None, None, 33000, "need_aware", "direct", "EA Nov 1 · RD Feb 15", "https://www.minerva.edu/admissions", "Global rotation through several cities; does not use SAT scores."),
    # ---------------------------------------------------------------- USA: public universities
    ("University of California, Berkeley", "USA", "Berkeley, CA", NA, "public", "top50", 11.6, None, None, "none", "blind", 6.5, 80, 52000, "limited", "direct", "UC app Nov 30", "https://admissions.berkeley.edu", "University of California campuses are test-blind."),
    ("University of California, Los Angeles (UCLA)", "USA", "Los Angeles, CA", NA, "public", "top50", 9.0, None, None, "none", "blind", 7.0, 100, 50000, "limited", "direct", "UC app Nov 30", "https://admission.ucla.edu", "Test-blind."),
    ("University of California, San Diego", "USA", "La Jolla, CA", NA, "public", "top100", 25.0, None, None, "none", "blind", 7.0, 83, 50000, "limited", "direct", "UC app Nov 30", "https://admissions.ucsd.edu", "Test-blind."),
    ("University of California, Davis", "USA", "Davis, CA", NA, "public", "top200", 42.0, None, None, "none", "blind", 6.5, 80, 49000, "limited", "direct", "UC app Nov 30", "https://www.ucdavis.edu/admissions", "Test-blind."),
    ("University of California, Irvine", "USA", "Irvine, CA", NA, "public", "top500", 26.0, None, None, "none", "blind", 6.5, 80, 50000, "limited", "direct", "UC app Nov 30", "https://admissions.uci.edu", "Test-blind."),
    ("University of California, Santa Barbara", "USA", "Santa Barbara, CA", NA, "public", "top500", 26.0, None, None, "none", "blind", 7.0, 80, 49000, "limited", "direct", "UC app Nov 30", "https://admissions.sa.ucsb.edu", "Test-blind."),
    ("University of Michigan", "USA", "Ann Arbor, MI", NA, "public", "top50", 18.0, 1350, 1530, "middle50", "optional", 6.5, 100, 61000, "limited", "common_app", "EA Nov 1 · RD Feb 1", "https://admissions.umich.edu", ""),
    ("University of Virginia", "USA", "Charlottesville, VA", NA, "public", "top500", 16.0, 1400, 1530, "middle50", "optional", 7.0, 100, 58000, "limited", "common_app", "ED/EA Nov 1 · RD Jan 5", "https://admission.virginia.edu", ""),
    ("University of North Carolina at Chapel Hill", "USA", "Chapel Hill, NC", NA, "public", "top200", 17.0, 1370, 1520, "middle50", "required", 6.5, 100, 42000, "limited", "common_app", "EA Oct 15 · RD Jan 15", "https://admissions.unc.edu", ""),
    ("Georgia Institute of Technology", "USA", "Atlanta, GA", NA, "public", "top200", 16.0, 1370, 1530, "middle50", "required", 7.0, 95, 34000, "limited", "common_app", "EA Oct 15/Nov 1 · RD Jan 4", "https://admission.gatech.edu", ""),
    ("University of Illinois Urbana-Champaign", "USA", "Champaign, IL", NA, "public", "top100", 43.0, 1340, 1530, "middle50", "optional", 6.5, 103, 40000, "limited", "common_app", "EA Nov 1 · RD Jan 5", "https://www.admissions.illinois.edu", "Engineering and computer science are far more selective than the overall rate."),
    ("University of Texas at Austin", "USA", "Austin, TX", NA, "public", "top100", 27.0, 1230, 1480, "middle50", "required", 6.5, 79, 46000, "limited", "common_app", "Priority Nov 1 · RD Dec 1", "https://admissions.utexas.edu", ""),
    ("University of Wisconsin–Madison", "USA", "Madison, WI", NA, "public", "top200", 43.0, 1340, 1490, "middle50", "optional", 6.5, 80, 43000, "limited", "common_app", "EA Nov 1 · RD Jan 15", "https://admissions.wisc.edu", ""),
    ("University of Washington", "USA", "Seattle, WA", NA, "public", "top100", 43.0, None, None, "none", "optional", 7.0, 92, 44000, "limited", "direct", "Nov 15", "https://admit.washington.edu", ""),
    ("Purdue University", "USA", "West Lafayette, IN", NA, "public", "top100", 50.0, 1190, 1430, "middle50", "required", 6.5, 80, 31000, "merit", "common_app", "EA Nov 1 · RD Jan 15", "https://admissions.purdue.edu", ""),
    ("Ohio State University", "USA", "Columbus, OH", NA, "public", "top200", 51.0, 1260, 1440, "middle50", "optional", 6.5, 79, 38000, "merit", "common_app", "EA Nov 1 · RD Feb 1", "https://undergrad.osu.edu", ""),
    ("Pennsylvania State University", "USA", "University Park, PA", NA, "public", "top100", 54.0, 1180, 1370, "middle50", "optional", 6.5, 80, 42000, "limited", "common_app", "EA Nov 1 · RD Feb 1", "https://admissions.psu.edu", ""),
    ("University of Maryland, College Park", "USA", "College Park, MD", NA, "public", "top200", 45.0, 1340, 1500, "middle50", "optional", 7.0, 100, 43000, "merit", "common_app", "EA Nov 1 · RD Jan 20", "https://admissions.umd.edu", ""),
    ("Virginia Tech", "USA", "Blacksburg, VA", NA, "public", "top500", 57.0, 1210, 1400, "middle50", "optional", 6.5, 80, 37000, "limited", "common_app", "ED Nov 1 · RD Jan 15", "https://admissions.vt.edu", ""),
    ("Texas A&M University", "USA", "College Station, TX", NA, "public", "top200", 63.0, 1160, 1390, "middle50", "required", 6.5, 80, 41000, "limited", "direct", "Dec 1", "https://admissions.tamu.edu", ""),
    ("University of Florida", "USA", "Gainesville, FL", NA, "public", "top500", 24.0, 1330, 1470, "middle50", "required", 6.0, 80, 29000, "limited", "common_app", "EA Nov 1 · RD Mar 1", "https://admissions.ufl.edu", ""),
    ("Rutgers University–New Brunswick", "USA", "New Brunswick, NJ", NA, "public", "top500", 66.0, 1240, 1440, "middle50", "optional", 6.5, 79, 36000, "limited", "direct", "EA Nov 1 · RD Dec 1", "https://admissions.rutgers.edu", ""),
    ("Stony Brook University", "USA", "Stony Brook, NY", NA, "public", "other", 49.0, 1290, 1470, "middle50", "optional", 6.5, 80, 30000, "merit", "common_app", "EA Dec 1 · RD Jan 15", "https://www.stonybrook.edu/admissions", ""),
    ("University of Pittsburgh", "USA", "Pittsburgh, PA", NA, "public", "top500", 49.0, 1250, 1430, "middle50", "optional", 6.5, 80, 38000, "merit", "common_app", "Rolling", "https://admissions.pitt.edu", ""),
    ("University of Minnesota Twin Cities", "USA", "Minneapolis, MN", NA, "public", "top200", 77.0, 1250, 1450, "middle50", "optional", 6.5, 79, 36000, "merit", "common_app", "EA Nov 1 · RD Jan 1", "https://admissions.tc.umn.edu", ""),
    ("Indiana University Bloomington", "USA", "Bloomington, IN", NA, "public", "top500", 80.0, 1180, 1390, "middle50", "optional", 6.5, 79, 41000, "merit", "common_app", "EA Nov 1 · RD Feb 1", "https://admissions.indiana.edu", ""),
    ("Michigan State University", "USA", "East Lansing, MI", NA, "public", "top200", 84.0, 1100, 1300, "middle50", "optional", 6.5, 79, 43000, "merit", "common_app", "EA Nov 1 · Rolling", "https://admissions.msu.edu", ""),
    ("Arizona State University", "USA", "Tempe, AZ", NA, "public", "top500", 90.0, 1130, 1350, "middle50", "optional", 6.0, 61, 35000, "merit", "direct", "Rolling", "https://admission.asu.edu", "New American University Scholarship for international students."),
    ("University of Arizona", "USA", "Tucson, AZ", NA, "public", "top500", 86.0, 1110, 1330, "middle50", "optional", 6.5, 70, 39000, "merit", "common_app", "Rolling", "https://admissions.arizona.edu", ""),
    ("University of Colorado Boulder", "USA", "Boulder, CO", NA, "public", "top500", 81.0, 1150, 1350, "middle50", "optional", 6.5, 75, 43000, "merit", "common_app", "EA Nov 15 · RD Jan 15", "https://www.colorado.edu/admissions", ""),
    ("Iowa State University", "USA", "Ames, IA", NA, "public", "other", 91.0, 1080, 1320, "middle50", "optional", 6.0, 71, 27000, "merit", "direct", "Rolling", "https://www.admissions.iastate.edu", ""),
    ("University of Utah", "USA", "Salt Lake City, UT", NA, "public", "other", 89.0, 1110, 1340, "middle50", "optional", 6.5, 80, 32000, "merit", "direct", "Rolling", "https://admissions.utah.edu", ""),
    ("Clemson University", "USA", "Clemson, SC", NA, "public", "other", 38.0, 1240, 1410, "middle50", "optional", 6.5, 80, 41000, "merit", "common_app", "EA Oct 15 · RD Jan 1", "https://www.clemson.edu/admissions", ""),
    # ---------------------------------------------------------------- United Kingdom (UCAS: SAT + 3 APs is the usual US-curriculum route)
    ("University of Oxford", "United Kingdom", "Oxford", EU, "public", "top10", 14.0, 1470, 1550, "minimum", "accepted", 7.5, 110, 52000, "limited", "ucas", "UCAS Oct 15", "https://www.ox.ac.uk/admissions/undergraduate", "SAT 1470+ plus three AP 5s or equivalent; admissions tests and interviews for most courses."),
    ("University of Cambridge", "United Kingdom", "Cambridge", EU, "public", "top10", 18.0, 1460, 1550, "minimum", "accepted", 7.5, 110, 52000, "limited", "ucas", "UCAS Oct 15", "https://www.undergraduate.study.cam.ac.uk", "SAT 1460–1500 plus AP 5s; interviews and course tests."),
    ("Imperial College London", "United Kingdom", "London", EU, "public", "top10", 13.0, 1500, 1570, "minimum", "accepted", 7.0, 100, 50000, "limited", "ucas", "UCAS Jan", "https://www.imperial.ac.uk/study/apply/undergraduate", "SAT plus several AP 5s in the subjects you will study."),
    ("University College London (UCL)", "United Kingdom", "London", EU, "public", "top10", 30.0, 1400, 1500, "minimum", "accepted", 7.0, 100, 43000, "limited", "ucas", "UCAS Jan", "https://www.ucl.ac.uk/prospective-students/undergraduate", ""),
    ("London School of Economics (LSE)", "United Kingdom", "London", EU, "public", "top50", 10.0, 1450, 1550, "minimum", "accepted", 7.0, 107, 39000, "limited", "ucas", "UCAS Jan", "https://www.lse.ac.uk/study-at-lse/undergraduate", ""),
    ("King's College London", "United Kingdom", "London", EU, "public", "top50", 13.0, 1350, 1450, "minimum", "accepted", 7.0, 100, 40000, "limited", "ucas", "UCAS Jan", "https://www.kcl.ac.uk/study/undergraduate", ""),
    ("University of Edinburgh", "United Kingdom", "Edinburgh", EU, "public", "top50", 10.0, 1290, 1400, "minimum", "accepted", 6.5, 92, 36000, "limited", "ucas", "UCAS Jan", "https://www.ed.ac.uk/studying/undergraduate", "Four-year Scottish degrees."),
    ("University of Manchester", "United Kingdom", "Manchester", EU, "public", "top50", 55.0, 1300, 1400, "minimum", "accepted", 6.5, 90, 36000, "limited", "ucas", "UCAS Jan", "https://www.manchester.ac.uk/study/undergraduate", ""),
    ("University of Warwick", "United Kingdom", "Coventry", EU, "public", "top100", 14.0, 1350, 1450, "minimum", "accepted", 6.5, 92, 39000, "limited", "ucas", "UCAS Jan", "https://warwick.ac.uk/study/undergraduate", ""),
    ("University of Bristol", "United Kingdom", "Bristol", EU, "public", "top100", 67.0, 1350, 1450, "minimum", "accepted", 6.5, 90, 37000, "limited", "ucas", "UCAS Jan", "https://www.bristol.ac.uk/study/undergraduate", ""),
    ("Durham University", "United Kingdom", "Durham", EU, "public", "top100", 40.0, 1350, 1450, "minimum", "accepted", 6.5, 92, 37000, "limited", "ucas", "UCAS Jan", "https://www.durham.ac.uk/study/undergraduate", ""),
    ("University of St Andrews", "United Kingdom", "St Andrews", EU, "public", "top200", 30.0, 1290, 1400, "minimum", "accepted", 7.0, 90, 40000, "limited", "ucas", "UCAS Jan (also Common App)", "https://www.st-andrews.ac.uk/subjects/entry/", "Accepts both UCAS and the Common App."),
    ("University of Glasgow", "United Kingdom", "Glasgow", EU, "public", "top100", 70.0, 1290, 1400, "minimum", "accepted", 6.5, 90, 34000, "limited", "ucas", "UCAS Jan", "https://www.gla.ac.uk/undergraduate", ""),
    ("University of Birmingham", "United Kingdom", "Birmingham", EU, "public", "top100", 70.0, 1300, 1400, "minimum", "accepted", 6.5, 88, 35000, "merit", "ucas", "UCAS Jan", "https://www.birmingham.ac.uk/undergraduate", ""),
    ("University of Leeds", "United Kingdom", "Leeds", EU, "public", "top100", 65.0, 1300, 1400, "minimum", "accepted", 6.5, 87, 35000, "merit", "ucas", "UCAS Jan", "https://www.leeds.ac.uk/undergraduate", ""),
    ("University of Southampton", "United Kingdom", "Southampton", EU, "public", "top100", 77.0, 1300, 1400, "minimum", "accepted", 6.5, 92, 34000, "merit", "ucas", "UCAS Jan", "https://www.southampton.ac.uk/courses/undergraduate", ""),
    ("University of Nottingham", "United Kingdom", "Nottingham", EU, "public", "top200", 70.0, 1250, 1350, "minimum", "accepted", 6.5, 87, 34000, "merit", "ucas", "UCAS Jan", "https://www.nottingham.ac.uk/ugstudy", ""),
    # ---------------------------------------------------------------- Europe
    ("ETH Zurich", "Switzerland", "Zurich", EU, "public", "top10", None, None, None, "none", "accepted", 7.0, 100, 1800, "limited", "direct", "Apr 30", "https://ethz.ch/en/studies/bachelor.html", "Most bachelor programmes are taught in German; non-Swiss diplomas may need an entrance exam."),
    ("EPFL", "Switzerland", "Lausanne", EU, "public", "top50", None, None, None, "none", "accepted", 7.0, 100, 1800, "limited", "direct", "Apr 30", "https://www.epfl.ch/education/admission/", "Bachelor teaching is mainly in French."),
    ("Technical University of Munich", "Germany", "Munich", EU, "public", "top50", None, 1300, 1450, "minimum", "accepted", 6.5, 88, 6000, "limited", "direct", "Jan 15 / May 31", "https://www.tum.de/en/studies/application", "Tuition for non-EU students since 2024; some English-taught bachelor programmes."),
    ("Ludwig Maximilian University of Munich", "Germany", "Munich", EU, "public", "top100", None, None, None, "none", "accepted", 6.5, 90, 400, "none", "direct", "Jan 15 / Jul 15", "https://www.lmu.de/en/study/", "Mostly German-taught; only a semester fee."),
    ("Heidelberg University", "Germany", "Heidelberg", EU, "public", "top100", None, None, None, "none", "accepted", 6.5, 90, 3300, "limited", "direct", "Jun 15", "https://www.uni-heidelberg.de/en/study", "Mostly German-taught."),
    ("Constructor University", "Germany", "Bremen", EU, "private", "other", None, 1250, 1400, "minimum", "recommended", 6.5, 90, 22000, "merit", "direct", "Rolling (Mar 1 priority)", "https://constructor.university/admission-aid", "English-taught; merit scholarships for high SAT scores."),
    ("University of Amsterdam", "Netherlands", "Amsterdam", EU, "public", "top100", None, 1300, 1450, "minimum", "accepted", 6.5, 92, 16000, "limited", "direct", "Jan 15 (selective) · May 1", "https://www.uva.nl/en/education/bachelor-s", "Apply through Studielink."),
    ("Delft University of Technology", "Netherlands", "Delft", EU, "public", "top50", None, 1350, 1500, "minimum", "accepted", 6.5, 90, 20000, "limited", "direct", "Jan 15", "https://www.tudelft.nl/en/education/admission-and-application", "Numerus fixus programmes have a selection procedure."),
    ("Leiden University", "Netherlands", "Leiden", EU, "public", "top200", None, 1300, 1450, "minimum", "accepted", 6.5, 90, 15000, "limited", "direct", "Jan 15 · May 1", "https://www.universiteitleiden.nl/en/education/admission-and-application", ""),
    ("KU Leuven", "Belgium", "Leuven", EU, "public", "top100", None, None, None, "none", "accepted", 6.5, 90, 7000, "limited", "direct", "Mar 1", "https://www.kuleuven.be/english/admissions", ""),
    ("Bocconi University", "Italy", "Milan", EU, "private", "top500", 20.0, 1350, 1500, "minimum", "accepted", 6.5, 95, 17000, "merit", "direct", "Early Nov · Feb · Apr rounds", "https://www.unibocconi.eu/admissions", "SAT is the main test for international applicants; merit awards for top scores."),
    ("Politecnico di Milano", "Italy", "Milan", EU, "public", "top200", None, 1250, 1450, "minimum", "accepted", 6.0, 80, 4200, "merit", "direct", "Several rounds Oct–Apr", "https://www.polimi.it/en/international-prospective-students", "SAT can replace the entrance test (TOL/TIL) for international applicants."),
    ("University of Bologna", "Italy", "Bologna", EU, "public", "top200", None, 1200, 1400, "minimum", "accepted", 6.0, 80, 3000, "merit", "direct", "Spring rounds", "https://www.unibo.it/en/study", "Several English-taught degrees accept SAT."),
    ("Sapienza University of Rome", "Italy", "Rome", EU, "public", "top200", None, 1200, 1400, "minimum", "accepted", 6.0, 80, 3000, "merit", "direct", "Spring rounds", "https://www.uniroma1.it/en/pagina/international-students", ""),
    ("University of Padua", "Italy", "Padua", EU, "public", "top500", None, 1200, 1400, "minimum", "accepted", 6.0, 80, 3000, "merit", "direct", "Spring rounds", "https://www.unipd.it/en/admission", ""),
    ("IE University", "Spain", "Madrid / Segovia", EU, "private", "other", None, 1200, 1400, "minimum", "accepted", 6.5, 90, 26000, "merit", "direct", "Rolling rounds", "https://www.ie.edu/university/admissions", ""),
    ("Trinity College Dublin", "Ireland", "Dublin", EU, "public", "top100", None, 1300, 1450, "minimum", "accepted", 6.5, 90, 28000, "limited", "direct", "Feb 1 (non-EU direct)", "https://www.tcd.ie/study/non-eu", ""),
    ("University College Dublin", "Ireland", "Dublin", EU, "public", "top200", None, 1250, 1400, "minimum", "accepted", 6.5, 90, 26000, "merit", "direct", "Rolling", "https://www.ucd.ie/global", ""),
    ("KTH Royal Institute of Technology", "Sweden", "Stockholm", EU, "public", "top100", None, None, None, "none", "accepted", 6.5, 90, 15000, "merit", "direct", "Jan 15 (master's) · Apr 15", "https://www.kth.se/en/studies", "Few English-taught bachelor programmes."),
    ("University of Copenhagen", "Denmark", "Copenhagen", EU, "public", "top100", None, None, None, "none", "accepted", 6.5, 83, 15000, "limited", "direct", "Mar 15", "https://studies.ku.dk/bachelor", ""),
    ("University of Helsinki", "Finland", "Helsinki", EU, "public", "top200", None, 1250, 1400, "minimum", "accepted", 6.5, 90, 15000, "merit", "direct", "Jan", "https://www.helsinki.fi/en/admissions-and-education", "SAT can be used for English-taught bachelor's programmes."),
    ("Sciences Po", "France", "Paris", EU, "public", "other", None, 1300, 1450, "minimum", "accepted", 7.0, 100, 15000, "need_aware", "direct", "Dec (early) · Feb", "https://www.sciencespo.fr/admissions", "Fees depend on family income."),
    ("Charles University", "Czech Republic", "Prague", EU, "public", "top500", None, None, None, "none", "accepted", 6.0, 80, 8000, "limited", "direct", "Feb–Apr", "https://cuni.cz/UKEN-1.html", "English-taught programmes charge tuition; Czech-taught are free."),
    ("Semmelweis University", "Hungary", "Budapest", EU, "public", "other", None, None, None, "none", "accepted", 6.0, 80, 18000, "limited", "direct", "Rolling", "https://semmelweis.hu/admissions", "Medicine in English; entrance exam in biology and chemistry."),
    ("Corvinus University of Budapest", "Hungary", "Budapest", EU, "public", "other", None, 1200, 1400, "minimum", "accepted", 6.0, 80, 6000, "merit", "direct", "Rolling", "https://www.uni-corvinus.hu/admission", "Stipendium Hungaricum scholarship covers tuition for eligible countries."),
    # ---------------------------------------------------------------- Asia
    ("National University of Singapore (NUS)", "Singapore", "Singapore", AS, "public", "top10", 10.0, 1450, 1550, "minimum", "required", 6.5, 92, 30000, "merit", "direct", "Feb", "https://www.nus.edu.sg/oam", "MOE Tuition Grant lowers fees in exchange for 3 years of work in Singapore."),
    ("Nanyang Technological University (NTU)", "Singapore", "Singapore", AS, "public", "top50", 15.0, 1400, 1550, "minimum", "required", 6.5, 92, 30000, "merit", "direct", "Feb", "https://www.ntu.edu.sg/admissions/undergraduate", "MOE Tuition Grant with a service bond."),
    ("University of Hong Kong (HKU)", "Hong Kong", "Hong Kong", AS, "public", "top50", None, 1350, 1500, "minimum", "accepted", 6.5, 93, 24000, "merit", "direct", "Nov (early) · Jan", "https://admissions.hku.hk", "Entrance scholarships for strong international applicants."),
    ("Hong Kong University of Science and Technology (HKUST)", "Hong Kong", "Hong Kong", AS, "public", "top50", None, 1400, 1500, "minimum", "accepted", 6.5, 80, 23000, "merit", "direct", "Nov (early) · Jan", "https://join.hkust.edu.hk", ""),
    ("Chinese University of Hong Kong (CUHK)", "Hong Kong", "Hong Kong", AS, "public", "top50", None, 1350, 1500, "minimum", "accepted", 6.5, 79, 23000, "merit", "direct", "Nov (early) · Jan", "https://admission.cuhk.edu.hk", ""),
    ("Tsinghua University", "China", "Beijing", AS, "public", "top50", None, None, None, "none", "accepted", 6.5, 90, 5000, "merit", "direct", "Dec–Mar", "https://www.join-tsinghua.edu.cn/en", "Chinese Government Scholarship can cover tuition and living costs."),
    ("Peking University", "China", "Beijing", AS, "public", "top50", None, None, None, "none", "accepted", 6.5, 90, 5000, "merit", "direct", "Dec–Mar", "https://isd.pku.edu.cn/en", "Chinese Government Scholarship available."),
    ("Fudan University", "China", "Shanghai", AS, "public", "top50", None, None, None, "none", "accepted", 6.5, 90, 4500, "merit", "direct", "Feb–Apr", "https://iso.fudan.edu.cn", ""),
    ("Zhejiang University", "China", "Hangzhou", AS, "public", "top50", None, None, None, "none", "accepted", 6.5, 90, 4000, "merit", "direct", "Feb–Apr", "https://iczu.zju.edu.cn", ""),
    ("University of Tokyo", "Japan", "Tokyo", AS, "public", "top50", None, 1400, 1550, "minimum", "required", 7.0, 100, 3700, "merit", "direct", "PEAK: Dec", "https://peak.c.u-tokyo.ac.jp", "PEAK is the English-taught undergraduate programme."),
    ("Kyoto University", "Japan", "Kyoto", AS, "public", "top50", None, None, None, "none", "accepted", 6.5, 90, 3700, "merit", "direct", "iUP: Oct–Dec", "https://iup.kyoto-u.ac.jp", "International Undergraduate Program teaches Japanese in year one."),
    ("Waseda University", "Japan", "Tokyo", AS, "private", "top200", None, 1300, 1450, "minimum", "accepted", 6.5, 90, 11000, "merit", "direct", "Several rounds", "https://www.waseda.jp/inst/admission/en", "English-based degree programmes (SILS, PSE, etc.)."),
    ("Keio University", "Japan", "Tokyo", AS, "private", "top200", None, 1300, 1450, "minimum", "accepted", 6.5, 90, 11000, "merit", "direct", "Several rounds", "https://www.keio.ac.jp/en/admissions", ""),
    ("Seoul National University", "South Korea", "Seoul", AS, "public", "top50", None, None, None, "none", "accepted", 6.5, 88, 7000, "merit", "direct", "Sep–Nov", "https://admission.snu.ac.kr/international", "Global Korea Scholarship (GKS) covers tuition and living costs."),
    ("KAIST", "South Korea", "Daejeon", AS, "public", "top100", None, 1350, 1500, "minimum", "accepted", 6.5, 83, 8000, "merit", "direct", "Rounds Nov–Mar", "https://admission.kaist.ac.kr/intl-undergraduate", "Most admitted international students receive full scholarships."),
    ("Yonsei University", "South Korea", "Seoul", AS, "private", "top100", None, 1350, 1500, "minimum", "accepted", 6.5, 88, 10000, "merit", "direct", "Rounds Nov–Mar", "https://admission.yonsei.ac.kr/seoul/admission/html/eng/main/main.asp", "Underwood International College teaches in English."),
    ("Korea University", "South Korea", "Seoul", AS, "private", "top100", None, None, None, "none", "accepted", 6.0, 80, 9000, "merit", "direct", "Rounds Nov–Mar", "https://oia.korea.ac.kr", ""),
    ("Sungkyunkwan University", "South Korea", "Seoul", AS, "private", "top200", None, None, None, "none", "accepted", 6.0, 80, 9000, "merit", "direct", "Rounds", "https://admission-global.skku.edu", ""),
    ("Universiti Malaya", "Malaysia", "Kuala Lumpur", AS, "public", "top100", None, None, None, "none", "accepted", 6.0, 80, 5000, "limited", "direct", "Rounds", "https://study.um.edu.my", ""),
    ("Nazarbayev University", "Kazakhstan", "Astana", AS, "public", "other", None, 1200, 1450, "minimum", "accepted", 6.5, 79, 0, "merit", "direct", "Spring rounds", "https://admissions.nu.edu.kz", "Grants cover tuition for admitted students; English-taught."),
    # ---------------------------------------------------------------- Middle East & Turkey
    ("NYU Abu Dhabi", "United Arab Emirates", "Abu Dhabi", ME, "private", "other", 4.0, 1450, 1560, "middle50", "optional", None, None, 60000, "need_blind", "common_app", "ED Nov 1 · RD Jan 5", "https://nyuad.nyu.edu/en/admissions.html", "Meets full demonstrated need for admitted students, including internationals."),
    ("Khalifa University", "United Arab Emirates", "Abu Dhabi", ME, "public", "top500", None, 1200, 1400, "minimum", "accepted", 6.0, 79, 0, "merit", "direct", "Rounds", "https://www.ku.ac.ae/admissions", "Scholarships cover tuition for admitted students."),
    ("American University of Sharjah", "United Arab Emirates", "Sharjah", ME, "private", "top500", None, 1150, 1350, "minimum", "accepted", 6.5, 80, 26000, "merit", "direct", "Rounds", "https://www.aus.edu/admissions", "Merit scholarships based on grades and SAT."),
    ("Carnegie Mellon University in Qatar", "Qatar", "Doha", ME, "private", "other", None, 1350, 1500, "middle50", "optional", 7.0, 100, 60000, "need_aware", "common_app", "ED Nov 1 · RD Jan 1", "https://www.qatar.cmu.edu/admission", "Same degree as CMU Pittsburgh; Qatar Foundation loans and aid."),
    ("Georgetown University in Qatar", "Qatar", "Doha", ME, "private", "other", None, 1300, 1480, "middle50", "optional", 7.0, 100, 58000, "need_aware", "direct", "EA Nov 1 · RD Jan 10", "https://www.qatar.georgetown.edu/admissions", ""),
    ("Koç University", "Turkey", "Istanbul", ME, "private", "top500", None, 1250, 1450, "minimum", "accepted", 6.5, 80, 25000, "merit", "direct", "Rounds Jan–Jun", "https://international.ku.edu.tr", "SAT-based merit scholarships up to full tuition."),
    ("Sabancı University", "Turkey", "Istanbul", ME, "private", "top500", None, 1200, 1400, "minimum", "accepted", 6.5, 80, 22000, "merit", "direct", "Rounds", "https://www.sabanciuniv.edu/en/international-students", ""),
    ("Bilkent University", "Turkey", "Ankara", ME, "private", "top500", None, 1150, 1400, "minimum", "accepted", 6.5, 87, 14000, "merit", "direct", "Rounds", "https://w3.bilkent.edu.tr/www/admissions/international", "Comprehensive scholarships for strong SAT scores."),
    ("Middle East Technical University (METU)", "Turkey", "Ankara", ME, "public", "top500", None, 1200, 1400, "minimum", "accepted", 6.5, 75, 3000, "limited", "direct", "Rounds", "https://iso.metu.edu.tr", "English-taught; SAT accepted for international applicants."),
    ("Boğaziçi University", "Turkey", "Istanbul", ME, "public", "top500", None, 1250, 1450, "minimum", "accepted", 6.5, 80, 3000, "limited", "direct", "Rounds", "https://bogazici.edu.tr/en-US/Content/Admission", "English-taught."),
    # ---------------------------------------------------------------- Canada
    ("University of Toronto", "Canada", "Toronto, ON", NA, "public", "top50", 43.0, None, None, "none", "recommended", 6.5, 100, 48000, "merit", "ouac", "Jan 15", "https://future.utoronto.ca", "Lester B. Pearson International Scholarship (school nomination by Nov)."),
    ("University of British Columbia", "Canada", "Vancouver, BC", NA, "public", "top50", 52.0, None, None, "none", "recommended", 6.5, 90, 40000, "merit", "direct", "Jan 15", "https://you.ubc.ca", "International Scholars Program (apply by Nov 15)."),
    ("McGill University", "Canada", "Montreal, QC", NA, "public", "top50", 45.0, 1350, 1500, "minimum", "recommended", 6.5, 90, 36000, "merit", "direct", "Jan 15", "https://www.mcgill.ca/undergraduate-admissions", "SAT recommended for US-curriculum applicants."),
    ("University of Waterloo", "Canada", "Waterloo, ON", NA, "public", "top200", 53.0, None, None, "none", "accepted", 6.5, 90, 47000, "merit", "ouac", "Feb 1", "https://uwaterloo.ca/future-students", "Co-op work terms in most programmes."),
    ("McMaster University", "Canada", "Hamilton, ON", NA, "public", "top200", 58.0, None, None, "none", "accepted", 6.5, 86, 38000, "merit", "ouac", "Jan 15", "https://future.mcmaster.ca", ""),
    ("University of Alberta", "Canada", "Edmonton, AB", NA, "public", "top200", 58.0, None, None, "none", "accepted", 6.5, 90, 26000, "merit", "direct", "Mar 1", "https://www.ualberta.ca/admissions", ""),
    ("Western University", "Canada", "London, ON", NA, "public", "top200", 58.0, None, None, "none", "accepted", 6.5, 83, 36000, "merit", "ouac", "Feb 1", "https://welcome.uwo.ca", ""),
    ("Queen's University", "Canada", "Kingston, ON", NA, "public", "top200", 42.0, None, None, "none", "accepted", 6.5, 88, 45000, "merit", "ouac", "Feb 1", "https://www.queensu.ca/admission", ""),
    ("University of Ottawa", "Canada", "Ottawa, ON", NA, "public", "top500", 69.0, None, None, "none", "accepted", 6.5, 86, 30000, "merit", "ouac", "Mar 1", "https://www.uottawa.ca/study", "Bilingual English/French university."),
    # ---------------------------------------------------------------- Australia & New Zealand
    ("Australian National University", "Australia", "Canberra", OC, "public", "top50", 35.0, 1300, 1450, "minimum", "accepted", 6.5, 80, 33000, "merit", "direct", "Rounds (main intake Feb)", "https://study.anu.edu.au", ""),
    ("University of Melbourne", "Australia", "Melbourne", OC, "public", "top50", None, 1300, 1450, "minimum", "accepted", 6.5, 79, 32000, "merit", "direct", "Rounds", "https://study.unimelb.edu.au", "Accepts SAT with a strong high-school record."),
    ("University of Sydney", "Australia", "Sydney", OC, "public", "top50", None, 1290, 1450, "minimum", "accepted", 6.5, 85, 35000, "merit", "direct", "Rounds", "https://www.sydney.edu.au/study", ""),
    ("UNSW Sydney", "Australia", "Sydney", OC, "public", "top50", None, 1300, 1450, "minimum", "accepted", 6.5, 90, 34000, "merit", "direct", "Rounds", "https://www.unsw.edu.au/study", ""),
    ("Monash University", "Australia", "Melbourne", OC, "public", "top50", None, 1250, 1400, "minimum", "accepted", 6.5, 79, 31000, "merit", "direct", "Rounds", "https://www.monash.edu/study", ""),
    ("University of Queensland", "Australia", "Brisbane", OC, "public", "top50", None, 1250, 1400, "minimum", "accepted", 6.5, 87, 31000, "merit", "direct", "Rounds", "https://study.uq.edu.au", ""),
    ("University of Western Australia", "Australia", "Perth", OC, "public", "top100", None, 1200, 1350, "minimum", "accepted", 6.5, 82, 28000, "merit", "direct", "Rounds", "https://www.uwa.edu.au/study", ""),
    ("University of Adelaide", "Australia", "Adelaide", OC, "public", "top100", None, 1200, 1350, "minimum", "accepted", 6.5, 79, 28000, "merit", "direct", "Rounds", "https://www.adelaide.edu.au/study", ""),
    ("University of Auckland", "New Zealand", "Auckland", OC, "public", "top100", None, 1200, 1350, "minimum", "accepted", 6.0, 80, 28000, "merit", "direct", "Dec 1 (Feb intake)", "https://www.auckland.ac.nz/en/study.html", ""),
]

FIELDS = (
    "name", "country", "city", "region", "kind", "rank_band", "acceptance_rate", "sat_low", "sat_high", "sat_kind",
    "test_policy", "ielts_min", "toefl_min", "tuition_usd", "aid", "platform", "deadlines", "website", "notes",
)


def _unique_slug(University, name):
    from django.utils.text import slugify

    base = slugify(name)[:200] or "university"
    slug, n = base, 2
    while University.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def load_universities(University, *, update=True):
    """Insert or update the seed rows (matched by name). Returns (created, updated)."""
    created = updated = 0
    for row in UNIVERSITIES:
        values = dict(zip(FIELDS, row))
        name = values.pop("name")
        obj = University.objects.filter(name=name).first()
        if obj is None:
            # Explicit slug: historical models in migrations do not run University.save().
            University.objects.create(name=name, slug=_unique_slug(University, name), **values)
            created += 1
        elif update:
            for key, value in values.items():
                setattr(obj, key, value)
            obj.save()
            updated += 1
    return created, updated
