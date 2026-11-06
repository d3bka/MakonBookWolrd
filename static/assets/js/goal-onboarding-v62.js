/* MakonBook V65: authenticated first-login prototype onboarding.
 * The account/guest/signup flow from the prototype is NOT used.
 * Existing Django CSRF, profile name endpoint and goal form remain authoritative.
 */
(() => {
  'use strict';
  const root = document.querySelector('[data-mb65-onboard]');
  if (!root) return;
  const form = root.querySelector('[data-goal-form]');
  const shell = root.querySelector('.mb65-shell');
  const panels = [...root.querySelectorAll('[data-mb65-step]')];
  const score = form.querySelector('[name="target_sat_score"]');
  const range = root.querySelector('[data-mb65-score-range]');
  const uni = form.querySelector('[name="university_choice"]');
  const exam = form.querySelector('[name="exam_date"]');
  const search = root.querySelector('[data-university-search]');
  const other = root.querySelector('[data-custom-university-fields]');
  const list = root.querySelector('[data-mb65-university-list]');
  const formAlert = root.querySelector('[data-goal-form-alert]');
  const nameRequired = root.dataset.nameRequired === '1';
  const firstGoal = root.dataset.firstGoal === '1';
  if (firstGoal && score?.value === '1400') score.value = '1450';
  let nameComplete = !nameRequired;
  let current = nameRequired ? 'name' : 'target';
  let searchQuery = '';
  let region = 'all';
  let wallOnly = false;
  let globe = null;
  const order = ['name','target','uni','date','ready'];
  const steps = nameRequired ? order : order.slice(1);
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const universityData = (() => { try {return JSON.parse(document.getElementById('student-goal-universities')?.textContent || '[]') || [];} catch (_) {return [];} })();
  const byId = new Map(universityData.map(u => [String(u.value),u]));
  const geos = {"Massachusetts Institute of Technology":[42.36,-71.094,"mit.edu",1],"Imperial College London":[51.498,-0.175,"imperial.ac.uk",0],"University of Oxford":[51.754,-1.254,"ox.ac.uk",1],"Harvard University":[42.377,-71.117,"harvard.edu",1],"University of Cambridge":[52.204,0.115,"cam.ac.uk",1],"Stanford University":[37.427,-122.17,"stanford.edu",1],"ETH Zurich":[47.376,8.548,"ethz.ch",0],"National University of Singapore":[1.297,103.776,"nus.edu.sg",1],"University College London":[51.525,-0.134,"ucl.ac.uk",0],"California Institute of Technology":[34.138,-118.125,"caltech.edu",1],"University of Hong Kong":[22.283,114.137,"hku.hk",1],"Nanyang Technological University":[1.348,103.683,"ntu.edu.sg",0],"University of Chicago":[41.789,-87.6,"uchicago.edu",1],"Peking University":[39.987,116.306,"pku.edu.cn",0],"University of Pennsylvania":[39.952,-75.193,"upenn.edu",1],"Cornell University":[42.453,-76.473,"cornell.edu",1],"Tsinghua University":[40.0,116.326,"tsinghua.edu.cn",1],"University of California, Berkeley":[37.872,-122.259,"berkeley.edu",1],"University of Melbourne":[-37.798,144.961,"unimelb.edu.au",0],"University of New South Wales":[-33.917,151.231,"unsw.edu.au",0],"Yale University":[41.316,-72.922,"yale.edu",1],"EPFL":[46.519,6.566,"epfl.ch",0],"Technical University of Munich":[48.149,11.568,"tum.de",1],"Johns Hopkins University":[39.33,-76.62,"jhu.edu",1],"Princeton University":[40.343,-74.651,"princeton.edu",1],"University of Sydney":[-33.889,151.19,"sydney.edu.au",1],"PSL University":[48.844,2.344,"psl.eu",0],"University of Tokyo":[35.713,139.762,"u-tokyo.ac.jp",1],"McGill University":[45.505,-73.577,"mcgill.ca",0],"Australian National University":[-35.278,149.12,"anu.edu.au",0],"Fudan University":[31.298,121.501,"fudan.edu.cn",0],"Institut Polytechnique de Paris":[48.713,2.211,"ip-paris.fr",0],"Columbia University":[40.808,-73.962,"columbia.edu",1],"University of Toronto":[43.663,-79.396,"utoronto.ca",1],"King's College London":[51.511,-0.116,"kcl.ac.uk",0],"University of Edinburgh":[55.944,-3.189,"ed.ac.uk",0],"Zhejiang University":[30.263,120.123,"zju.edu.cn",0],"University of California, Los Angeles":[34.069,-118.445,"ucla.edu",1],"University of Manchester":[53.467,-2.234,"manchester.ac.uk",0],"Shanghai Jiao Tong University":[31.025,121.434,"sjtu.edu.cn",0],"Chinese University of Hong Kong":[22.42,114.207,"cuhk.edu.hk",0],"University of Michigan":[42.278,-83.738,"umich.edu",1],"Monash University":[-37.911,145.134,"monash.edu",0],"Kyoto University":[35.026,135.781,"kyoto-u.ac.jp",0],"University of British Columbia":[49.261,-123.246,"ubc.ca",0],"Seoul National University":[37.46,126.952,"snu.ac.kr",0],"Hong Kong University of Science and Technology":[22.337,114.263,"hkust.edu.hk",0],"University of Malaya":[3.122,101.654,"um.edu.my",1],"London School of Economics":[51.514,-0.117,"lse.ac.uk",0],"University of Queensland":[-27.497,153.013,"uq.edu.au",0],"University of Buenos Aires":[-34.599,-58.373,"uba.ar",1],"New York University":[40.729,-73.996,"nyu.edu",0],"Northwestern University":[42.056,-87.675,"northwestern.edu",1],"KU Leuven":[50.878,4.7,"kuleuven.be",0],"Delft University of Technology":[51.999,4.373,"tudelft.nl",0],"University of Amsterdam":[52.356,4.955,"uva.nl",1],"Carnegie Mellon University":[40.443,-79.943,"cmu.edu",1],"KAIST":[36.372,127.36,"kaist.ac.kr",0],"Yonsei University":[37.566,126.939,"yonsei.ac.kr",1],"Duke University":[36.001,-78.938,"duke.edu",1],"City University of Hong Kong":[22.337,114.172,"cityu.edu.hk",0],"Sorbonne University":[48.846,2.357,"sorbonne-universite.fr",0],"Ludwig Maximilian University of Munich":[48.151,11.58,"lmu.de",0],"Hong Kong Polytechnic University":[22.304,114.18,"polyu.edu.hk",0],"Korea University":[37.589,127.032,"korea.ac.kr",0],"University of Auckland":[-36.852,174.769,"auckland.ac.nz",1],"National Taiwan University":[25.017,121.54,"ntu.edu.tw",0],"University of California San Diego":[32.88,-117.234,"ucsd.edu",0],"Brown University":[41.827,-71.403,"brown.edu",1],"University of Bristol":[51.458,-2.603,"bristol.ac.uk",0],"University of Texas at Austin":[30.285,-97.734,"utexas.edu",0],"University of Warwick":[52.38,-1.561,"warwick.ac.uk",0],"University of São Paulo":[-23.561,-46.73,"usp.br",0],"Heidelberg University":[49.41,8.706,"uni-heidelberg.de",0],"University of Illinois Urbana-Champaign":[40.102,-88.227,"illinois.edu",0],"University of Washington":[47.655,-122.308,"washington.edu",0],"Trinity College Dublin":[53.344,-6.254,"tcd.ie",0],"Osaka University":[34.822,135.524,"osaka-u.ac.jp",0],"Moscow State University":[55.703,37.531,"msu.ru",0],"KTH Royal Institute of Technology":[59.35,18.07,"kth.se",0],"University of Copenhagen":[55.68,12.572,"ku.dk",0],"Institute of Science Tokyo":[35.605,139.684,"isct.ac.jp",0],"University of Western Australia":[-31.98,115.818,"uwa.edu.au",0],"Pohang University of Science and Technology":[36.012,129.322,"postech.ac.kr",0],"National Autonomous University of Mexico":[19.332,-99.187,"unam.mx",0],"Georgia Institute of Technology":[33.776,-84.398,"gatech.edu",0],"University of Glasgow":[55.872,-4.288,"gla.ac.uk",0],"Pontifical Catholic University of Chile":[-33.442,-70.64,"uc.cl",0],"Lund University":[55.712,13.203,"lu.se",1],"University of Adelaide":[-34.919,138.605,"adelaide.edu.au",0],"Free University of Berlin":[52.453,13.29,"fu-berlin.de",0],"University of Zurich":[47.375,8.549,"uzh.ch",0],"Boston University":[42.35,-71.105,"bu.edu",0],"University of Southampton":[50.935,-1.396,"southampton.ac.uk",0],"Purdue University":[40.424,-86.921,"purdue.edu",0],"University of Leeds":[53.807,-1.555,"leeds.ac.uk",0],"University of Birmingham":[52.45,-1.93,"birmingham.ac.uk",0],"King Fahd University of Petroleum and Minerals":[26.307,50.146,"kfupm.edu.sa",1],"University of Waterloo":[43.472,-80.544,"uwaterloo.ca",0],"Rice University":[29.717,-95.402,"rice.edu",1],"Vanderbilt University":[36.145,-86.803,"vanderbilt.edu",1],"NYU Abu Dhabi":[24.524,54.434,"nyuad.nyu.edu",1],"Carnegie Mellon University in Qatar":[25.316,51.437,"qatar.cmu.edu",1],"Sciences Po":[48.854,2.329,"sciencespo.fr",1],"Sapienza University of Rome":[41.903,12.515,"uniroma1.it",1],"Westminster International University in Tashkent":[41.338,69.29,"wiut.uz",0],"Inha University in Tashkent":[41.341,69.335,"inha.uz",0],"Turin Polytechnic University in Tashkent":[41.346,69.205,"polito.uz",0]};


  const sel = q => root.querySelector(q);
  const text = (q,value) => {const el=sel(q);if(el)el.textContent=String(value == null ? '' : value);};
  const emitChange = el => el.dispatchEvent(new Event('change',{bubbles:true}));
  const normalized = s => String(s||'').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/\b(the|university|college|of|and)\b/g,'').replace(/[^a-z0-9]/g,'');
  const catalogueGeoV653 = {"massachusettsinstitutetechnologymit":[42.36,-71.094,"mit.edu",1,"reference"],"imperiallondon":[51.498,-0.175,"imperial.ac.uk",0,"reference"],"stanford":[37.427,-122.17,"stanford.edu",1,"reference"],"oxford":[51.754,-1.254,"ox.ac.uk",1,"reference"],"harvard":[42.377,-71.117,"harvard.edu",1,"reference"],"cambridge":[52.204,0.115,"cam.ac.uk",1,"reference"],"californiainstitutetechnologycaltech":[34.138,-118.125,"caltech.edu",1,"reference"],"ethzurich":[47.376,8.548,"ethz.ch",0,"reference"],"ucl":[51.525,-0.134,"ucl.ac.uk",0,"reference"],"nationalsingaporenus":[1.297,103.776,"nus.edu.sg",1,"reference"],"hongkong":[22.283,114.137,"hku.hk",1,"reference"],"nanyangtechnologicalsingaporentusingapore":[1.352,103.82,"",0,"city"],"peking":[39.987,116.306,"pku.edu.cn",0,"reference"],"tsinghua":[40.0,116.326,"tsinghua.edu.cn",1,"reference"],"pennsylvania":[39.952,-75.193,"upenn.edu",1,"reference"],"cornell":[42.453,-76.473,"cornell.edu",1,"reference"],"yale":[41.316,-72.922,"yale.edu",1,"reference"],"chinesehongkongcuhk":[22.42,114.207,"cuhk.edu.hk",0,"reference"],"newsouthwalesunswsydney":[-33.917,151.231,"unsw.edu.au",0,"reference"],"johnshopkins":[39.33,-76.62,"jhu.edu",1,"reference"],"californiaberkeleyucb":[37.872,-122.259,"berkeley.edu",1,"reference"],"epflecolepolytechniquefederaledelausanne":[46.519,6.633,"",0,"city"],"melbourne":[-37.798,144.961,"unimelb.edu.au",0,"reference"],"chicago":[41.789,-87.6,"uchicago.edu",1,"reference"],"technicalmunich":[48.149,11.568,"tum.de",1,"reference"],"fudan":[31.298,121.501,"fudan.edu.cn",0,"reference"],"princeton":[40.343,-74.651,"princeton.edu",1,"reference"],"sydney":[-33.889,151.19,"sydney.edu.au",1,"reference"],"australiannationalanu":[-35.278,149.12,"anu.edu.au",0,"reference"],"mcgill":[45.505,-73.577,"mcgill.ca",0,"reference"],"monash":[-37.911,145.134,"monash.edu",0,"reference"],"toronto":[43.663,-79.396,"utoronto.ca",1,"reference"],"hongkongsciencetechnology":[22.337,114.263,"hkust.edu.hk",0,"reference"],"universitepsl":[48.844,2.344,"psl.eu",0,"reference"],"edinburgh":[55.944,-3.189,"ed.ac.uk",0,"reference"],"shanghaijiaotong":[31.025,121.434,"sjtu.edu.cn",0,"reference"],"kingslondon":[51.511,-0.116,"kcl.ac.uk",0,"reference"],"seoulnational":[37.46,126.952,"snu.ac.kr",0,"reference"],"tokyo":[35.713,139.762,"u-tokyo.ac.jp",1,"reference"],"manchester":[53.467,-2.234,"manchester.ac.uk",0,"reference"],"queensland":[-27.497,153.013,"uq.edu.au",0,"reference"],"yonsei":[37.566,126.939,"yonsei.ac.kr",1,"reference"],"columbia":[40.808,-73.962,"columbia.edu",1,"reference"],"institutpolytechniquedeparis":[48.713,2.211,"ip-paris.fr",0,"reference"],"northwestern":[42.056,-87.675,"northwestern.edu",1,"reference"],"britishcolumbia":[49.261,-123.246,"ubc.ca",0,"reference"],"zhejiang":[30.263,120.123,"zju.edu.cn",0,"reference"],"delfttechnology":[51.999,4.373,"tudelft.nl",0,"reference"],"californialosangelesucla":[34.069,-118.445,"ucla.edu",1,"reference"],"hongkongpolytechnic":[22.304,114.18,"polyu.edu.hk",0,"reference"],"michiganannarbor":[42.281,-83.743,"",0,"city"],"cityhongkongcityuhk":[22.337,114.172,"cityu.edu.hk",0,"reference"],"korea":[37.589,127.032,"korea.ac.kr",0,"reference"],"nationaltaiwanntu":[25.017,121.54,"ntu.edu.tw",0,"reference"],"carnegiemellon":[40.443,-79.943,"cmu.edu",1,"reference"],"universitimalayaum":[3.122,101.654,"um.edu.my",1,"reference"],"bristol":[51.458,-2.603,"bristol.ac.uk",0,"reference"],"newyorknyu":[40.729,-73.996,"nyu.edu",0,"reference"],"kuleuven":[50.878,4.7,"kuleuven.be",0,"reference"],"amsterdam":[52.356,4.955,"uva.nl",1,"reference"],"ludwigmaximiliansuniversitatmunchen":[48.135,11.582,"",0,"city"],"londonschooleconomicspoliticalsciencelse":[51.507,-0.128,"",0,"city"],"kfupm":[26.284,50.116,"",0,"city"],"kyoto":[35.026,135.781,"kyoto-u.ac.jp",0,"reference"],"kaist":[36.372,127.36,"kaist.ac.kr",0,"reference"],"brown":[41.827,-71.403,"brown.edu",1,"reference"],"auckland":[-36.852,174.769,"auckland.ac.nz",1,"reference"],"warwick":[52.38,-1.561,"warwick.ac.uk",0,"reference"],"birmingham":[52.45,-1.93,"birmingham.ac.uk",0,"reference"],"duke":[36.001,-78.938,"duke.edu",1,"reference"],"lund":[55.712,13.203,"lu.se",1,"reference"],"texasataustin":[30.285,-97.734,"utexas.edu",0,"reference"],"sorbonne":[48.846,2.357,"sorbonne-universite.fr",0,"reference"],"illinoisurbanachampaign":[40.102,-88.227,"illinois.edu",0,"reference"],"trinitydublindublin":[53.35,-6.26,"",0,"city"],"universiteparissaclay":[48.857,2.352,"",0,"city"],"westernaustralia":[-31.98,115.818,"uwa.edu.au",0,"reference"],"leeds":[53.807,-1.555,"leeds.ac.uk",0,"reference"],"adelaide":[-34.919,138.605,"adelaide.edu.au",0,"reference"],"glasgow":[55.872,-4.288,"gla.ac.uk",0,"reference"],"californiasandiegoucsd":[32.88,-117.234,"ucsd.edu",0,"reference"],"kthroyalinstitutetechnology":[59.35,18.07,"kth.se",0,"reference"],"sheffield":[53.381,-1.47,"",0,"city"],"universidaddebuenosairesuba":[-34.599,-58.373,"uba.ar",1,"reference"],"durham":[54.775,-1.584,"",0,"city"],"universitatheidelberg":[49.399,8.672,"",0,"city"],"politecnicodimilano":[45.464,9.19,"",0,"city"],"technologysydneyuts":[-33.869,151.209,"",0,"city"],"uppsala":[59.859,17.639,"",0,"city"],"nanjing":[32.061,118.797,"",0,"city"],"copenhagen":[55.68,12.572,"ku.dk",0,"reference"],"pennsylvaniastate":[40.797,-77.861,"",0,"city"],"washington":[47.655,-122.308,"washington.edu",0,"reference"],"boston":[42.35,-71.105,"bu.edu",0,"reference"],"osaka":[34.822,135.524,"osaka-u.ac.jp",0,"reference"],"alberta":[53.546,-113.494,"",0,"city"],"institutesciencetokyo":[35.605,139.684,"isct.ac.jp",0,"reference"],"nottingham":[52.954,-1.159,"",0,"city"],"freieuniversitaetberlin":[52.52,13.405,"",0,"city"],"zurich":[47.375,8.549,"uzh.ch",0,"reference"],"purdue":[40.424,-86.921,"purdue.edu",0,"reference"],"dublin":[53.35,-6.26,"",0,"city"],"tohoku":[38.268,140.87,"",0,"city"],"queenmarylondon":[51.507,-0.128,"",0,"city"],"rwthaachen":[50.776,6.084,"",0,"city"],"technicaldenmark":[55.772,12.502,"",0,"city"],"pohangsciencetechnologypostech":[36.012,129.322,"postech.ac.kr",0,"reference"],"kingsaud":[24.714,46.675,"",0,"city"],"sungkyunkwanskku":[37.566,126.978,"",0,"city"],"qatar":[25.286,51.533,"",0,"city"],"kitkarlsruheinstitutetechnology":[49.007,8.404,"",0,"city"],"sapienzarome":[41.903,12.515,"uniroma1.it",1,"reference"],"southampton":[50.935,-1.396,"southampton.ac.uk",0,"reference"],"waterloo":[43.472,-80.544,"uwaterloo.ca",0,"reference"],"utrecht":[52.09,5.122,"",0,"city"],"lomonosovmoscowstate":[55.703,37.531,"msu.ru",0,"reference"],"standrews":[56.34,-2.801,"",0,"city"],"indianinstitutetechnologydelhiiitd":[28.614,77.209,"",0,"city"],"leiden":[52.16,4.497,"",0,"city"],"pontificiauniversidadcatolicadechileuc":[-33.449,-70.669,"",0,"city"],"rmit":[-37.814,144.963,"",0,"city"],"rice":[29.717,-95.402,"rice.edu",1,"reference"],"almamaterstudiorumuniversitadibologna":[44.494,11.343,"",0,"city"],"helsinki":[60.17,24.938,"",0,"city"],"bath":[51.381,-2.359,"",0,"city"],"aalto":[60.205,24.655,"",0,"city"],"macquariesydneyaustralia":[-33.869,151.209,"",0,"city"],"aarhus":[56.158,10.21,"",0,"city"],"universitisainsmalaysiausm":[5.368,100.306,"",0,"city"],"universitikebangsaanmalaysiaukm":[2.923,101.784,"",0,"city"],"oslo":[59.913,10.752,"",0,"city"],"wisconsinmadison":[43.073,-89.401,"",0,"city"],"universidadedesaopaulo":[-23.55,-46.633,"",0,"city"],"indianinstitutetechnologybombayiitb":[19.076,72.878,"",0,"city"],"sciencetechnologychina":[31.82,117.227,"",0,"city"],"exeter":[50.719,-3.533,"",0,"city"],"californiadavis":[38.545,-121.74,"",0,"city"],"universitiputramalaysiaupm":[2.995,101.716,"",0,"city"],"liverpool":[53.408,-2.991,"",0,"city"],"humboldtuniversitatzuberlin":[52.52,13.405,"",0,"city"],"vienna":[48.208,16.374,"",0,"city"],"georgiainstitutetechnology":[33.776,-84.398,"gatech.edu",0,"reference"],"nationaltsinghuanthu":[24.805,120.972,"",0,"city"],"western":[42.985,-81.245,"",0,"city"],"universidadnacionalautonomademexicounam":[19.433,-99.133,"",0,"city"],"tongji":[31.23,121.473,"",0,"city"],"khalifa":[24.453,54.377,"",0,"city"],"erasmusrotterdam":[51.924,4.478,"",0,"city"],"newcastle":[54.978,-1.618,"",0,"city"],"ghent":[51.054,3.725,"",0,"city"],"basel":[47.559,7.588,"",0,"city"],"eindhoventechnology":[51.442,5.479,"",0,"city"],"southerncalifornia":[34.052,-118.244,"",0,"city"],"wageningenresearch":[51.97,5.665,"",0,"city"],"hanyang":[37.566,126.978,"",0,"city"],"nagoya":[35.181,136.906,"",0,"city"],"groningen":[53.219,6.566,"",0,"city"],"technischeuniversitatberlintuberlin":[52.52,13.405,"",0,"city"],"universititeknologimalaysia":[1.536,103.663,"",0,"city"],"northcarolinaatchapelhill":[35.913,-79.056,"",0,"city"],"york":[53.96,-1.087,"",0,"city"],"universitedemontreal":[45.502,-73.567,"",0,"city"],"washingtoninstlouis":[38.627,-90.199,"",0,"city"],"lancaster":[54.047,-2.801,"",0,"city"],"universitatdebarcelona":[41.388,2.17,"",0,"city"],"wuhan":[30.593,114.305,"",0,"city"],"stockholm":[59.329,18.069,"",0,"city"],"geneva":[46.204,6.143,"",0,"city"],"texasam":[30.628,-96.334,"",0,"city"],"indianinstitutetechnologymadrasiitm":[13.083,80.271,"",0,"city"],"kyushu":[33.59,130.402,"",0,"city"],"arizonastate":[33.448,-112.074,"",0,"city"],"californiasantabarbaraucsb":[34.421,-119.698,"",0,"city"],"chalmerstechnology":[57.708,11.974,"",0,"city"],"mcmaster":[43.255,-79.872,"",0,"city"],"queensbelfast":[54.598,-5.93,"",0,"city"],"alfarabikazakhnational":[43.238,76.945,"",0,"city"],"nationalyangmingchiaotungnycutaiwan":[24.805,120.972,"",0,"city"],"cardiff":[51.481,-3.179,"",0,"city"],"hokkaido":[43.062,141.354,"",0,"city"],"queensatkingston":[44.232,-76.486,"",0,"city"],"michiganstate":[42.736,-84.484,"",0,"city"],"emory":[33.749,-84.388,"",0,"city"],"capetown":[-33.925,18.424,"",0,"city"],"technischeuniversitatdresden":[51.05,13.738,"",0,"city"],"universidaddechile":[-33.449,-70.669,"",0,"city"],"vrijeuniversiteitamsterdam":[52.368,4.904,"",0,"city"],"tecnologicodemonterrey":[25.687,-100.316,"",0,"city"],"curtin":[-31.953,115.861,"",0,"city"],"harbininstitutetechnology":[45.803,126.535,"",0,"city"],"nationalchengkungncku":[22.999,120.227,"",0,"city"],"technischeuniversitatwien":[48.208,16.374,"",0,"city"],"universitasindonesia":[-6.402,106.794,"",0,"city"],"bern":[46.948,7.447,"",0,"city"],"wollongong":[-34.427,150.893,"",0,"city"],"universitecatholiquedelouvainuclouvain":[50.668,4.612,"",0,"city"],"reading":[51.454,-0.978,"",0,"city"],"otago":[-45.878,170.503,"",0,"city"],"complutensemadrid":[40.417,-3.703,"",0,"city"],"kingabdulazizkau":[21.485,39.192,"",0,"city"]};
  const geoByName = new Map(Object.entries(geos).map(([key,value]) => [normalized(key),value]));
  const countries = {'usa':'United States','uk':'United Kingdom'};
  const getGeo = u => {
    if (!u) return null;
    const n=normalized(u.name);
    if (Object.prototype.hasOwnProperty.call(catalogueGeoV653,n)) return catalogueGeoV653[n];
    const hit=geoByName.get(n);
    if (hit) return hit;
    try {const host=new URL(u.website || '', location.href).hostname.replace(/^www\./,'');
      return Object.values(geos).find(x => x[2] && (host === x[2] || host.endsWith('.'+x[2]))) || null;
    } catch (_) {return null;}
  };
  const regionOf = u => {
    const c=(u.country||'').toLowerCase();const geo=getGeo(u);
    if(c.includes('united states')||c.includes('usa'))return 'us';
    if(c.includes('united kingdom')||c==='uk')return 'uk';
    if(c.includes('australia')||c.includes('new zealand'))return 'oc';
    if(c.includes('canada')||c.includes('mexico')||c.includes('brazil')||c.includes('argentina')||c.includes('chile'))return 'am';
    if(c.includes('uzbek')||c.includes('saudi')||c.includes('qatar')||c.includes('emirates'))return 'me';
    if(c.includes('japan')||c.includes('china')||c.includes('korea')||c.includes('india')||c.includes('malaysia')||c.includes('hong kong')||c.includes('singapore')||c.includes('taiwan'))return 'asia';
    return geo ? 'eu' : 'all';
  };
  const visibleUnis = () => universityData.filter(u => {
    const hay=(u.name+' '+u.country+' '+(u.city||'')).toLowerCase();
    return (!searchQuery||hay.includes(searchQuery))&&(!wallOnly || (getGeo(u)&&getGeo(u)[3]))&&(region==='all'||regionOf(u)===region);
  });
  function chosen() {return byId.get(uni.value) || null;}
  function selectedName(){return chosen()?.name || (uni.value==='other' ? (form.elements.custom_university_name?.value || 'Other university') : 'Choose your university');}
  function scoreValue(){return Number(score.value)||1400;}
  function examDate(){return exam.value || '';}
  function prettyDate(value){if(!value)return 'Choose a date'; const d=new Date(value+'T12:00:00');return Number.isNaN(d.getTime())?value:d.toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'});}
  function daysUntil(value){const d=new Date(value+'T12:00:00');return Number.isNaN(d.getTime())?null:Math.max(0,Math.ceil((d.getTime()-Date.now())/86400000));}
  function showError(message,focus){if(formAlert){formAlert.textContent=message;formAlert.hidden=false;}if(focus?.focus)focus.focus({preventScroll:false});}
  function clearError(){if(formAlert){formAlert.textContent='';formAlert.hidden=true;}}
  function currentName(){const f=sel('[data-mb65-first-name]')?.value?.trim();const l=sel('[data-mb65-last-name]')?.value?.trim();return [f,l].filter(Boolean).join(' ') || sel('[data-mb65-preview-name]')?.textContent?.trim()||'Student';}
  function updatePreview(){
    const index=steps.indexOf(current);
    const scoreKnown = !firstGoal || ['uni','date','ready'].includes(current);
    const uniKnown = !firstGoal || ['date','ready'].includes(current);
    const dateKnown = !firstGoal || ['ready'].includes(current);
    text('[data-mb65-preview-name]',currentName());
    text('[data-mb65-avatar]',currentName().charAt(0).toUpperCase());
    text('[data-mb65-preview-score]',scoreKnown?scoreValue():'Step '+(nameRequired?2:1));
    text('[data-mb65-preview-university]',uniKnown?selectedName():'Step '+(nameRequired?3:2));
    text('[data-mb65-preview-date]',dateKnown?prettyDate(examDate()):'Step '+(nameRequired?4:3));
    text('[data-mb65-preview-days]',dateKnown&&examDate()?daysUntil(examDate()):'—');
    text('[data-mb65-watermark]',scoreValue());
    // The large number is handled by animateScore(), never overwritten here.
    text('[data-mb65-ready-name]',currentName().split(/\s+/)[0]+'.');
    text('[data-mb65-ready-description]',`Target ${scoreValue()}, dream university ${selectedName()}, and ${daysUntil(examDate()) ?? '—'} days to prepare. Your first practice test will show your real starting score.`);
  }
  const bigScore = sel('[data-mb65-big-score]');
  let scoreFrame = 0;
  let scoreShown = Number(bigScore?.textContent?.trim()) || scoreValue();
  let scorePulse = 0;
  function animateScore(to, animated) {
    if (!bigScore) return;
    if (scoreFrame) cancelAnimationFrame(scoreFrame);
    scoreFrame = 0;
    const from = Number.isFinite(scoreShown) ? scoreShown : to;
    if (!animated || prefersReduced.matches || Math.abs(to - from) < 10) {
      scoreShown=to;
      bigScore.textContent=String(to);
      bigScore.classList.remove('is-counting');
      return;
    }
    const started=performance.now();
    const duration=470;
    // Animate from the number currently visible instead of jumping to the next preset.
    bigScore.classList.remove('is-counting');
    void bigScore.offsetWidth;
    bigScore.classList.add('is-counting');
    const tick = now => {
      const t=Math.max(0,Math.min(1,(now-started)/duration));
      const eased=1-Math.pow(1-t,3);
      scoreShown=Math.round((from+(to-from)*eased)/10)*10;
      bigScore.textContent=String(t>=1?to:scoreShown);
      if (t<1)scoreFrame=requestAnimationFrame(tick);
      else {
        scoreFrame=0;
        scoreShown=to;
        bigScore.classList.remove('is-counting');
      }
    };
    scoreFrame=requestAnimationFrame(tick);
  }
  function syncScore(animate=true){
    const num=Math.max(400,Math.min(1600,Math.round((Number(score.value)||1400)/10)*10));
    range.value=String(num);
    animateScore(num,animate);
    root.querySelectorAll('[data-mb65-preset]').forEach(b => b.classList.toggle('is-selected',Number(b.dataset.mb65Preset)===num));
    updatePreview();
  }
  range.addEventListener('input',()=>{score.value=range.value;emitChange(score);syncScore();});
  score.addEventListener('input',syncScore);
  root.querySelectorAll('[data-mb65-preset]').forEach(b => b.addEventListener('click',()=>{score.value=b.dataset.mb65Preset;emitChange(score);syncScore();}));
  root.querySelectorAll('[data-mb65-first-name],[data-mb65-last-name]').forEach(b => b.addEventListener('input',updatePreview));

  function showStep(key){
    if (!steps.includes(key))return;
    current=key;clearError();
    panels.forEach(p=>{p.hidden=p.dataset.mb65Step!==key;});
    const index=steps.indexOf(key);
    const ready=key==='ready';
    const progress=sel('[data-mb65-progress]');
    if (progress){progress.replaceChildren();steps.slice(0,-1).forEach((_,i)=>{const item=document.createElement('span');item.classList.toggle('on',i<=index);progress.appendChild(item);});}
    text('[data-mb65-step-label]',ready?'Your SAT plan is ready':`Step ${index+1} of ${steps.length-1}`);
    sel('[data-mb65-back]').hidden=index===0;
    sel('[data-mb65-next]').hidden=ready;
    sel('[data-goal-submit]').hidden=!ready;
    sel('[data-mb65-next]').textContent=key==='date'?'Finish setup →':key==='uni'?'Continue →':'Continue →';
    shell.classList.toggle('mb65-wide',key==='uni');
    const right=sel('.mb65-right');if(right)right.scrollTop=0;
    const wizardBody=sel('.mb65-body');if(wizardBody)wizardBody.scrollTop=0;
    if(key==='target') syncScore(false);
    if(globe && key!=='uni')globe.pause();
    if(key==='uni'){drawList();if(!globe)globe=createGlobe();if(globe){globe.activate();globe.refresh();}}
    if(key==='date')renderDates();
    if(ready){updatePreview();}
    updatePreview();
  }
  function getCookie(name){try{return document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith(name+'='))?.split('=').slice(1).join('=') || '';}catch(_){return '';}}
  async function saveName(){
    const first=sel('[data-mb65-first-name]').value.trim(),last=sel('[data-mb65-last-name]').value.trim();
    const error=sel('[data-mb65-name-error]');
    if(first.length<2||last.length<2){error.textContent='Enter your first and last name (at least 2 letters each).';return false;}
    const formData=new FormData();formData.append('first_name',first);formData.append('last_name',last);
    const token=form.querySelector('[name="csrfmiddlewaretoken"]')?.value || decodeURIComponent(getCookie('makonbook_csrftoken_v35')||getCookie('csrftoken')||'');
    formData.append('csrfmiddlewaretoken',token);
    const button=sel('[data-mb65-next]');button.disabled=true;button.textContent='Saving…';
    try{
      const response=await fetch(root.dataset.profileEndpoint,{method:'POST',body:formData,credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest','X-CSRFToken':token}});
      const body=await response.json();
      if(!response.ok||!body.ok){error.textContent=Object.values(body.errors||{}).join(' ')||'Could not save your name. Try again.';return false;}
      nameComplete=true;error.textContent='';document.querySelector('[data-profile-name-gate]')?.remove();updatePreview();return true;
    } catch(_){error.textContent='Network error. Check your connection and try again.';return false;}
    finally{button.disabled=false;button.textContent='Continue →';}
  }
  function validStep(step){
    clearError();
    if(step==='target') {const value=Number(score.value);
      if(!Number.isInteger(value)||value<400||value>1600||value%10!==0){showError('Choose a SAT score from 400 to 1600, in steps of 10.',score);return false;}}
    if(step==='uni'){
      if(!uni.value){showError('Choose a university from the catalogue.',search);return false;}
      if(uni.value==='other'){
        for(const [key,label] of [['custom_university_name','university name'],['custom_university_country','country'],['custom_average_sat_score','SAT reference score']]){
          const input=form.elements[key];if(!input||!String(input.value||'').trim()){showError('Enter the '+label+'.',input);return false;}}
      }
      const candidate=chosen();
      const sat=candidate?.average_sat_score||Number(form.elements.custom_average_sat_score?.value)||0;
      if(sat&&scoreValue()<sat){showError(`Your target must be at least the university SAT reference (${sat}).`,score);return false;}
    }
    if(step==='date'){
      if(!exam.value){showError('Choose an official SAT administration date.');return false;}
      const minutes=Number(form.elements.daily_study_minutes_goal?.value),days=Number(form.elements.weekly_study_days_goal?.value);
      if(minutes<15||minutes>360||days<1||days>7){showError('Choose 15–360 study minutes and 1–7 days per week.');return false;}
    }
    return true;
  }
  sel('[data-mb65-next]').addEventListener('click',async()=>{
    if(current==='name' && !(await saveName()))return;
    if(!validStep(current))return;
    const next=steps[steps.indexOf(current)+1];if(next)showStep(next);
  });
  sel('[data-mb65-back]').addEventListener('click',()=>{
    const index=steps.indexOf(current);if(index<=0)return;
    const back=steps[index-1];if(back==='name'&&nameComplete){showStep('target');return;}
    showStep(back);
  });
  root.addEventListener('click',event=>{
    const close=event.target.closest('[data-goal-modal-close]');
    if(close && !nameComplete){event.preventDefault();event.stopImmediatePropagation();showStep('name');showError('Please save your name first.');}
  },true);
  form.addEventListener('submit',event=>{
    if(current!=='ready'||!nameComplete){event.preventDefault();event.stopImmediatePropagation();return;}
    // Validate all steps, opening the actual invalid step for correction.
    for(const step of ['target','uni','date']){
      if(!validStep(step)){
        const message=formAlert?.textContent || 'Please review this step.';
        event.preventDefault();event.stopImmediatePropagation();showStep(step);showError(message);return;
      }
    }
    // The real Django POST persists the goal; no local demo account is created.
  },true);
  const practiceButton=sel('[data-mb65-practice]');if(practiceButton)practiceButton.addEventListener('click',()=>{
    const nextField=form.querySelector('[name="next"]');
    if(nextField && root.dataset.practiceUrl)nextField.value=root.dataset.practiceUrl;
    form.requestSubmit(sel('[data-goal-submit]'));
  });
  uni.addEventListener('change',()=>{updatePreview();drawList();if(globe)globe.refresh();
    text('[data-mb65-next]','Continue →');});
  [form.elements.custom_university_name,exam].filter(Boolean).forEach(el=>el.addEventListener('change',updatePreview));

  const regionOptions=[['all','World'],['us','USA'],['uk','UK'],['eu','Europe'],['asia','Asia'],['oc','Oceania'],['am','Americas'],['me','Middle East & Central Asia']];
  const regionEl=sel('[data-mb65-regions]');
  for(const [key,title] of regionOptions){const b=document.createElement('button');b.type='button';b.dataset.region=key;b.textContent=title;
    b.addEventListener('click',()=>{region=key;drawList();if(globe)globe.region(key);});regionEl.appendChild(b);}
  function pickUniversity(value){uni.value=value;emitChange(uni);updatePreview();drawList();if(globe)globe.focus(chosen());}
  function drawList(){
    regionEl.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b.dataset.region===region));
    const values=visibleUnis();text('[data-university-search-result]',`${values.length} universities · catalogue choices are official MakonBook data.`);
    list.replaceChildren();
    const append=(value,name,country,rank,sat)=>{
      const btn=document.createElement('button');btn.type='button';btn.dataset.uni=value;btn.setAttribute('role','option');btn.setAttribute('aria-selected',String(uni.value===value));
      const r=document.createElement('b');r.className='rank';r.textContent=rank?'#'+rank:'–';
      const txt=document.createElement('span');const st=document.createElement('strong');st.textContent=name;const sm=document.createElement('small');sm.textContent=country||'';txt.append(st,sm);
      btn.append(r,txt);if(sat){const em=document.createElement('em');em.textContent='≈'+sat;btn.appendChild(em);}
      btn.addEventListener('click',()=>pickUniversity(value));list.appendChild(btn);
    };
    values.forEach(u=>append(u.value,u.name,u.country,u.qs_rank,u.average_sat_score));
    if(region==='all'&&!searchQuery&&!wallOnly)append('other','Others — university not listed','Manual entry','',null);
    if(!list.children.length){const msg=document.createElement('p');msg.textContent='No matching universities. Try another country or name.';list.appendChild(msg);}
    const data=chosen();const card=sel('[data-mb65-selected-university]');card.replaceChildren();
    const st=document.createElement('strong');st.textContent=selectedName();card.appendChild(st);
    if(data){const meta=document.createElement('small');meta.textContent=(data.qs_rank?'#'+data.qs_rank+' · ':'')+data.country;card.appendChild(meta);
      const d=document.createElement('span');d.textContent=data.average_sat_score?'SAT reference: '+data.average_sat_score:'SAT reference not published';card.appendChild(d);
      const location=getGeo(data);if(location&&location[4]==='city'){const hint=document.createElement('span');hint.className='mb653-location-hint';hint.textContent='Map marker: approximate city location, not the exact campus';card.appendChild(hint);}}
  }
  search.addEventListener('input',()=>{searchQuery=search.value.trim().toLowerCase();if(searchQuery)region='all';drawList();if(globe)globe.refresh();});
  sel('[data-mb65-wall]').addEventListener('click',()=>{wallOnly=!wallOnly;sel('[data-mb65-wall]').classList.toggle('is-selected',wallOnly);drawList();if(globe)globe.refresh();});
  function renderDates(){const host=sel('[data-mb65-dates]');host.replaceChildren();
    [...exam.options].filter(o=>o.value).forEach(option=>{
      const b=document.createElement('button');b.type='button';b.classList.toggle('is-selected',exam.value===option.value);
      const txt=document.createElement('span');const st=document.createElement('strong');st.textContent=prettyDate(option.value);
      const sm=document.createElement('small');sm.textContent=`${daysUntil(option.value)} days to prepare`;txt.append(st,sm);
      const dot=document.createElement('span');dot.className='radio';b.append(txt,dot);
      b.addEventListener('click',()=>{exam.value=option.value;emitChange(exam);renderDates();updatePreview();});host.appendChild(b);
    });
    if(!host.children.length){const p=document.createElement('p');p.textContent='No future SAT dates currently configured. Please contact the administrator.';host.appendChild(p);}
  }

  // V65.3 — accurate orthographic surface and university markers.
  // A geography raster is inversely projected onto the globe, so shorelines never
  // mutate or form long triangles when they cross the horizon during rotation.
  function createGlobe() {
    const mount = sel('[data-mb65-globe]');
    if (!mount) return null;
    const NS = 'http://www.w3.org/2000/svg';
    const node = (tag, attributes={}) => {
      const el = document.createElementNS(NS, tag);
      for (const [k,v] of Object.entries(attributes)) el.setAttribute(k,String(v));
      return el;
    };
    const normalize = n => ((n + 180) % 360 + 360) % 360 - 180;
    const clamp = (n,lo,hi) => Math.max(lo,Math.min(hi,n));
    const ease = t => t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t+2,3)/2;
    const shortest = (from,to) => normalize(to-from);
    const tau = Math.PI / 180;
    const stage = document.createElement('div');
    stage.className = 'mb653-globe-stage';
    const canvas = document.createElement('canvas');
    canvas.width = 440; canvas.height = 440;
    canvas.className = 'mb653-earth-surface';
    canvas.setAttribute('aria-hidden','true');
    const context = canvas.getContext('2d',{alpha:true});
    const svg = node('svg',{viewBox:'0 0 500 500',role:'group',
      'aria-label':'University globe: drag to rotate. Select a marker or choose a university from the list.'});
    svg.classList.add('mb653-globe-overlay');
    const defs = node('defs');
    const clip = node('clipPath',{id:'mb653Clip'});
    clip.appendChild(node('circle',{cx:250,cy:250,r:218}));
    defs.appendChild(clip);svg.appendChild(defs);
    const circle=node('circle',{cx:250,cy:250,r:218,fill:'transparent',stroke:'#b996f2','stroke-width':2.1});
    svg.appendChild(circle);
    const world=node('g',{'clip-path':'url(#mb653Clip)'});svg.appendChild(world);
    const graticule=node('g',{fill:'none',stroke:'#e1d3f3','stroke-width':'.8','pointer-events':'none'});
    const pins=node('g');world.append(graticule,pins);
    const focusRing=node('g',{class:'mb652-focus-ring','pointer-events':'none'});
    focusRing.append(node('circle',{r:23,class:'mb652-focus-halo'}),node('circle',{r:10,class:'mb652-focus-core'}));
    world.appendChild(focusRing);
    stage.append(canvas,svg);mount.replaceChildren(stage);

    let centerLon=20,centerLat=22,zoom=1,active=false,drag=false,start=null;
    let pointerId=null,lastDragMove=0,dragSpeed=0,raf=0,nowLast=0,paintLast=0,motion=null,dirty=true;
    let mask=null,maskWidth=0,maskHeight=0;
    const image = new Image();
    image.decoding = 'async';
    image.onload = () => {
      try {
        const buffer=document.createElement('canvas');buffer.width=image.naturalWidth;buffer.height=image.naturalHeight;
        const bc=buffer.getContext('2d',{willReadFrequently:true});bc.drawImage(image,0,0);
        const rgba=bc.getImageData(0,0,buffer.width,buffer.height).data;
        mask=new Uint8Array(buffer.width*buffer.height);
        for(let i=0;i<mask.length;i++)mask[i]=rgba[i*4+3];
        maskWidth=buffer.width;maskHeight=buffer.height;dirty=true;
        if(!active)draw();
      } catch(error){console.warn('[MakonBook] Geographic mask could not be read:',error);}
    };
    image.onerror = () => console.warn('[MakonBook] Land mask not loaded; globe interactions remain available.');
    image.src=root.dataset.mb653Landmask || '/static/assets/img/world/gshhg_land_mask_2048.png';

    const surface=context && context.createImageData(canvas.width,canvas.height);
    const gridX=[],gridY=[],gridRad=[];
    const N=canvas.width, R=N*218/500;
    for(let y=0;y<N;y++)for(let x=0;x<N;x++){
      const dx=((x+.5)-N/2)/R,dy=(N/2-(y+.5))/R;
      gridX.push(dx);gridY.push(dy);gridRad.push(dx*dx+dy*dy);
    }
    function renderSurface(){
      if(!surface || !context)return;
      const pixels=surface.data;
      const slat=Math.sin(centerLat*tau),clat=Math.cos(centerLat*tau);
      const lo0=centerLon*tau;
      const zz=zoom;
      for(let i=0;i<gridRad.length;i++){
        const off=i*4, raw=gridRad[i];
        if(raw>1){pixels[off+3]=0;continue;}
        const x=gridX[i]/zz,y=gridY[i]/zz;
        const r2=x*x+y*y;
        if(r2>=1){pixels[off+3]=0;continue;}
        const z=Math.sqrt(1-r2);
        const lat=Math.asin(clamp(y*clat+z*slat,-1,1));
        const lon=lo0+Math.atan2(x,z*clat-y*slat);
        const mapLon=normalize(lon/tau);
        const mx=Math.min(maskWidth-1,Math.max(0,Math.floor((mapLon+180)/360*maskWidth)));
        const my=Math.min(maskHeight-1,Math.max(0,Math.floor((90-lat/tau)/180*maskHeight)));
        const landAlpha=mask ? mask[my*maskWidth+mx]/255 : 0;
        // Gentle directional lighting, but never a shape transformation.
        const light=clamp(.86+.12*z+.055*(-x+y),.72,1.05);
        const sea=[244*light,236*light,255*light];
        const earth=[175*light,153*light,219*light];
        pixels[off]=sea[0]*(1-landAlpha)+earth[0]*landAlpha;
        pixels[off+1]=sea[1]*(1-landAlpha)+earth[1]*landAlpha;
        pixels[off+2]=sea[2]*(1-landAlpha)+earth[2]*landAlpha;
        pixels[off+3]=255;
      }
      context.putImageData(surface,0,0);
    }
    function project(lat,lon){
      const phi=lat*tau,phi0=centerLat*tau,d=normalize(lon-centerLon)*tau;
      const depth=Math.sin(phi0)*Math.sin(phi)+Math.cos(phi0)*Math.cos(phi)*Math.cos(d);
      return {x:250+218*zoom*Math.cos(phi)*Math.sin(d),
              y:250-218*zoom*(Math.cos(phi0)*Math.sin(phi)-Math.sin(phi0)*Math.cos(phi)*Math.cos(d)),depth};
    }
    function segment(points){
      let output='',drawing=false;
      for(const [lon,lat] of points){const p=project(lat,lon);
        if(p.depth<0 || Math.hypot(p.x-250,p.y-250)>218){drawing=false;continue;}
        output+=(drawing?'L':'M')+p.x.toFixed(1)+','+p.y.toFixed(1);drawing=true;
      } return output;
    }
    function draw(){
      if(!root.isConnected)return;
      renderSurface();graticule.replaceChildren();pins.replaceChildren();
      svg.dataset.globeLongitude=centerLon.toFixed(2);
      svg.dataset.globeLatitude=centerLat.toFixed(2);
      svg.dataset.globeZoom=zoom.toFixed(3);
      for(let lat=-60;lat<=60;lat+=30){const pts=Array.from({length:181},(_,i)=>[-180+i*2,lat]);
        graticule.appendChild(node('path',{d:segment(pts)}));}
      for(let lon=-180;lon<180;lon+=30){const pts=Array.from({length:91},(_,i)=>[lon,-90+i*2]);
        graticule.appendChild(node('path',{d:segment(pts)}));}
      // Cluster overlapping universities, preserving actual point positions.
      // Click a cluster again to cycle universities at the same city/campus.
      const groups=[]; let mappedCount=0;
      for(const u of visibleUnis()){
        const geo=getGeo(u);if(!geo)continue;
        mappedCount++;
        const p=project(geo[0],geo[1]);
        if(p.depth<0.015||Math.hypot(p.x-250,p.y-250)>215)continue;
        let group=groups.find(g=>Math.hypot(g.x-p.x,g.y-p.y)<12);
        if(!group){group={x:p.x,y:p.y,members:[]};groups.push(group);}
        group.members.push({u,geo});
      }
      svg.dataset.geoMappedCount=String(mappedCount);
      svg.dataset.pointCount=String(groups.length);
      for(const group of groups){
        const selectedItem=group.members.find(m=>m.u.value===uni.value);
        const selected=Boolean(selectedItem);
        const r=selected?9:group.members.length>1?6.9:5.2;
        const dot=node('circle',{cx:group.x,cy:group.y,r,fill:selected?'#7c3aed':'#fff',
          stroke:'#7c3aed','stroke-width':selected?2.7:1.8,role:'button',tabindex:0,
          'data-uni-pin':'1','aria-label':group.members.map(x=>x.u.name).join(', '),
          class:selected?'mb653-dot-selected':'mb653-dot'});
        const title=node('title');title.textContent=group.members.map(m=>m.u.name+(m.geo[2]==='city'?' (approximate city location)':'')).join(' · ');
        dot.appendChild(title);
        function activatePoint(){
          let idx=group.members.findIndex(x=>x.u.value===uni.value);
          idx=(idx+1)%group.members.length;
          pickUniversity(group.members[idx].u.value);
        }
        dot.addEventListener('click',event=>{event.stopPropagation();activatePoint();});
        dot.addEventListener('pointerdown',event=>event.stopPropagation());
        dot.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();activatePoint();}});
        pins.appendChild(dot);
        if(group.members.length>1){const count=node('text',{x:group.x+7,y:group.y-7,
          class:'mb653-cluster-count','pointer-events':'none'});count.textContent=String(group.members.length);pins.appendChild(count);}
        if(selected){const label=node('text',{x:group.x+12,y:group.y+16,
          class:'mb653-pin-label','pointer-events':'none'});
          label.textContent=selectedItem.u.name.length>27?selectedItem.u.name.slice(0,25)+'…':selectedItem.u.name;
          pins.appendChild(label);}
      }
      const chosenGeo=getGeo(chosen());const focus=chosenGeo&&project(chosenGeo[0],chosenGeo[1]);
      if(focus&&focus.depth>.025&&Math.hypot(focus.x-250,focus.y-250)<218){
        focusRing.style.display='';focusRing.setAttribute('transform',`translate(${focus.x.toFixed(2)},${focus.y.toFixed(2)})`);
      }else focusRing.style.display='none';
      dirty=false;
    }
    function refresh(){dirty=true;if(!active)requestAnimationFrame(draw);}
    function flyTo(lon,lat,z,duration=980){
      lon=normalize(lon);lat=clamp(lat,-78,78);z=clamp(z,1,2.4);
      if(prefersReduced.matches){motion=null;centerLon=lon;centerLat=lat;zoom=z;refresh();return;}
      motion={at:performance.now(),duration,startLon:centerLon,delta:shortest(centerLon,lon),
        startLat:centerLat,targetLat:lat,startZoom:zoom,targetZoom:z};
      dirty=true;activate();
    }
    function frame(now){
      if(!active)return;
      raf=requestAnimationFrame(frame);
      if(document.hidden||current!=='uni'||!root.classList.contains('is-open')){nowLast=now;return;}
      const dt=Math.min(60,nowLast?now-nowLast:0);nowLast=now;
      let moving=false;
      if(motion){
        const t=clamp((now-motion.at)/motion.duration,0,1),v=ease(t);
        centerLon=normalize(motion.startLon+motion.delta*v);
        centerLat=motion.startLat+(motion.targetLat-motion.startLat)*v;
        zoom=motion.startZoom+(motion.targetZoom-motion.startZoom)*v;
        moving=true;if(t>=1)motion=null;
      }else if(!drag&&!prefersReduced.matches&&!uni.value){
        centerLon=normalize(centerLon+dt*.0043);moving=true;
      }
      const interval=window.innerWidth<600?65:50;
      if((moving||dirty)&&(now-paintLast>=interval||dirty)){draw();paintLast=now;}
    }
    function activate(){if(active)return;active=true;nowLast=0;paintLast=0;raf=requestAnimationFrame(frame);}
    function pause(){active=false;cancelAnimationFrame(raf);raf=0;motion=null;nowLast=0;}
    function stopMotion(){motion=null;}
    svg.addEventListener('pointerdown',e=>{
      if(e.target.closest('[data-uni-pin]'))return;
      if(e.button!==0&&e.pointerType==='mouse')return;
      stopMotion();drag=true;pointerId=e.pointerId;start=[e.clientX,e.clientY];lastDragMove=performance.now();dragSpeed=0;
      try{svg.setPointerCapture(e.pointerId);}catch(_){/* unsupported */}
    });
    svg.addEventListener('pointermove',e=>{
      if(!drag||pointerId!==e.pointerId)return;
      const dx=e.clientX-start[0],dy=e.clientY-start[1],now=performance.now();
      dragSpeed=.75*dragSpeed+.25*(dx/Math.max(16,now-lastDragMove));lastDragMove=now;
      centerLon=normalize(centerLon-dx*.42/zoom);
      centerLat=clamp(centerLat+dy*.35/zoom,-78,78);
      start=[e.clientX,e.clientY];dirty=true;
    });
    function release(){if(!drag)return;drag=false;pointerId=null;
      if(!prefersReduced.matches&&Math.abs(dragSpeed)>.2)flyTo(centerLon-clamp(dragSpeed*25,-26,26),centerLat,zoom,350);
    }
    svg.addEventListener('pointerup',release);svg.addEventListener('pointercancel',release);
    svg.addEventListener('lostpointercapture',release);
    svg.addEventListener('wheel',e=>{e.preventDefault();flyTo(centerLon,centerLat,zoom*(e.deltaY<0?1.12:.89),320);},{passive:false});
    sel('[data-mb65-zoom="in"]').addEventListener('click',()=>flyTo(centerLon,centerLat,zoom*1.22,340));
    sel('[data-mb65-zoom="out"]').addEventListener('click',()=>flyTo(centerLon,centerLat,zoom*.82,340));
    return {
      refresh,activate,pause,
      focus(u){const geo=getGeo(u);if(geo)flyTo(geo[1],geo[0],Math.max(1.55,zoom),1100);else refresh();},
      region(k){const views={all:[20,22,1],us:[-98,36,1.8],uk:[-1,53,2.1],eu:[17,50,1.8],
        asia:[105,29,1.5],oc:[144,-23,1.65],am:[-78,-8,1.2],me:[54,30,1.7]};
        const v=views[k]||views.all;flyTo(v[0],v[1],v[2],950);}
    };
  }
  root.querySelectorAll('[data-goal-modal-open]');
  document.querySelectorAll('[data-goal-modal-open]').forEach(button=>button.addEventListener('click',()=>{showStep(nameComplete?'target':'name');}));
  // Keep first login tied to verified Django account, no browser localStorage.
  syncScore(false);showStep(current);
})();
