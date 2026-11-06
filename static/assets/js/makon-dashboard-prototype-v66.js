/* MakonBook V66 — presentation-only behavior, no demo data or API requests. */
(function(){
 'use strict';
 var dashboard=document.querySelector('.mb66-dashboard');
 if(!dashboard)return;
 var dateText=dashboard.getAttribute('data-exam-date');
 var date=dateText?new Date(dateText+'T00:00:00'):null;
 var num=dashboard.querySelector('[data-mb66-countdown]');
 if(date&&num&&!isNaN(date.getTime())){
   var days=Math.max(0,Math.ceil((date.getTime()-Date.now())/86400000));
   num.textContent=days.toLocaleString('en-US');
 }
 var calendar=dashboard.querySelector('[data-mb66-calendar]');
 var monthLabel=dashboard.querySelector('[data-mb66-month]');
 if(calendar&&monthLabel){
   var now=new Date(),year=now.getFullYear(),month=now.getMonth();
   function paintCalendar(){
     calendar.textContent='';
     monthLabel.textContent=new Intl.DateTimeFormat('en-US',{month:'long',year:'numeric'}).format(new Date(year,month,1));
     var first=(new Date(year,month,1).getDay()+6)%7;
     for(var i=0;i<42;i++){
       var day=new Date(year,month,i-first+1);
       var cell=document.createElement('span');
       cell.textContent=day.getDate();
       if(day.getMonth()!==month)cell.classList.add('is-other');
       if(day.getFullYear()===now.getFullYear()&&day.getMonth()===now.getMonth()&&day.getDate()===now.getDate()){
         cell.classList.add('is-today');cell.setAttribute('aria-current','date');
       }
       if(date&&day.getFullYear()===date.getFullYear()&&day.getMonth()===date.getMonth()&&day.getDate()===date.getDate()){
         cell.classList.add('is-exam');cell.title='Your SAT exam date';
       }
       calendar.appendChild(cell);
     }
   }
   var prev=dashboard.querySelector('[data-mb66-prev-month]');
   var next=dashboard.querySelector('[data-mb66-next-month]');
   if(prev)prev.addEventListener('click',function(){var d=new Date(year,month-1,1);year=d.getFullYear();month=d.getMonth();paintCalendar()});
   if(next)next.addEventListener('click',function(){var d=new Date(year,month+1,1);year=d.getFullYear();month=d.getMonth();paintCalendar()});
   paintCalendar();
 }
})();
