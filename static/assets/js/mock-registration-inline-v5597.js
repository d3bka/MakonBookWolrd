(function () {
  'use strict';

  function qs(root, selector) { return root.querySelector(selector); }
  function qsa(root, selector) { return Array.prototype.slice.call(root.querySelectorAll(selector)); }

  function setStep(dialog, name) {
    qsa(dialog, '[data-step]').forEach(function (step) {
      step.hidden = step.getAttribute('data-step') !== name;
    });
    hideError(dialog);
    hideWarning(dialog);
    dialog.dataset.currentStep = name;
    var focusable = qs(dialog, '[data-step="' + name + '"] input:not([type="hidden"]), [data-step="' + name + '"] button, [data-step="' + name + '"] a');
    if (focusable) window.setTimeout(function () { try { focusable.focus({ preventScroll: true }); } catch (_) { focusable.focus(); } }, 40);
  }

  function showError(dialog, message) {
    var box = qs(dialog, '[data-inline-error]');
    if (!box) return;
    box.textContent = message || 'Something went wrong. Please try again.';
    box.hidden = false;
  }

  function hideError(dialog) {
    var box = qs(dialog, '[data-inline-error]');
    if (box) box.hidden = true;
  }

  function hideWarning(dialog) {
    var box = qs(dialog, '[data-email-warning]');
    if (box) box.hidden = true;
  }

  function showEmailWarning(dialog, payload, form) {
    var box = qs(dialog, '[data-email-warning]');
    if (!box) return;
    var copy = qs(box, '[data-email-warning-copy]');
    var suggestion = payload.suggested_email || payload.masked_suggested_email || '';
    if (copy) copy.textContent = (payload.error || 'Please check the email address.') + (suggestion ? ' Suggested: ' + suggestion + '.' : '');
    dialog._emailRetryForm = form;
    box.hidden = false;
  }

  function csrf(dialog) {
    var input = qs(dialog, 'input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function post(url, data, dialog) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json',
        'X-CSRFToken': csrf(dialog)
      },
      body: data,
      credentials: 'same-origin'
    }).then(function (response) {
      return response.json().catch(function () { return { ok: false, error: 'Unexpected server response.' }; }).then(function (payload) {
        payload._status = response.status;
        return payload;
      });
    });
  }

  function setBusy(form, busy) {
    if (!form) return;
    qsa(form, 'button, input').forEach(function (node) {
      if (node.type === 'hidden') return;
      node.disabled = !!busy;
    });
    form.classList.toggle('is-busy', !!busy);
  }

  function handlePending(dialog, payload) {
    if (payload.confirmed) {
      complete(dialog, payload);
      return;
    }
    dialog.dataset.verifyUrl = payload.verify_url || '';
    dialog.dataset.resendUrl = payload.resend_url || '';
    dialog.dataset.initialStep = 'verify';
    var email = qs(dialog, '[data-verify-email]');
    if (email) email.textContent = payload.masked_email || 'your email';
    setStep(dialog, 'verify');
  }

  function complete(dialog, payload) {
    var id = qs(dialog, '[data-registration-id]');
    if (id && payload.registration_id) id.textContent = payload.registration_id;
    dialog.dataset.initialStep = 'success';
    setStep(dialog, 'success');
  }

  function requestOrWarn(dialog, form, url, onSuccess) {
    hideError(dialog);
    hideWarning(dialog);
    var formData = new FormData(form);
    setBusy(form, true);
    post(url, formData, dialog).then(function (payload) {
      if (!payload.ok) {
        if (payload.can_override) showEmailWarning(dialog, payload, form);
        else showError(dialog, payload.error);
        return;
      }
      onSuccess(payload);
    }).catch(function () {
      showError(dialog, 'Could not connect to the server. Please try again.');
    }).finally(function () {
      setBusy(form, false);
    });
  }


  function setupFieldFeedbackReset(dialog) {
    qsa(dialog, 'input').forEach(function (input) {
      input.addEventListener('input', function () {
        hideError(dialog);
        hideWarning(dialog);
        var note = qs(dialog, '[data-inline-note]');
        if (note) note.hidden = true;
      });
      input.addEventListener('focus', function () {
        hideError(dialog);
      });
    });
  }

  function setup(dialog) {
    setupFieldFeedbackReset(dialog);

    qsa(document, '[data-mock-open="' + dialog.id + '"]').forEach(function (button) {
      button.addEventListener('click', function () {
        setStep(dialog, dialog.dataset.currentStep || dialog.dataset.initialStep || 'overview');
        if (typeof dialog.showModal === 'function') dialog.showModal();
        else dialog.setAttribute('open', '');
        document.documentElement.classList.add('mb597-modal-open');
      });
    });

    qsa(dialog, '[data-mock-close]').forEach(function (button) {
      button.addEventListener('click', function () {
        if (typeof dialog.close === 'function') dialog.close();
        else dialog.removeAttribute('open');
      });
    });
    dialog.addEventListener('close', function () { document.documentElement.classList.remove('mb597-modal-open'); });

    qsa(dialog, '[data-register-kind]').forEach(function (button) {
      button.addEventListener('click', function () {
        setStep(dialog, button.dataset.registerKind === 'external' ? 'external' : 'student');
      });
    });
    qsa(dialog, '[data-step-back]').forEach(function (button) {
      button.addEventListener('click', function () { setStep(dialog, button.dataset.stepBack || 'overview'); });
    });

    var lookup = qs(dialog, '[data-student-lookup]');
    if (lookup) lookup.addEventListener('submit', function (event) {
      event.preventDefault();
      requestOrWarn(dialog, lookup, dialog.dataset.studentUrl, function (payload) {
        var uid = qs(dialog, '[data-student-user-id]');
        var uname = qs(dialog, '[data-student-username]');
        var name = qs(dialog, '[data-student-name]');
        var email = qs(dialog, '[data-student-email]');
        if (uid) uid.value = payload.student_user_id || '';
        if (uname) uname.value = payload.username || '';
        if (name) name.textContent = payload.display_name || payload.username || 'Student account';
        if (email) email.textContent = payload.masked_email || 'the saved email';
        setStep(dialog, 'student-password');
      });
    });

    var password = qs(dialog, '[data-student-password]');
    if (password) password.addEventListener('submit', function (event) {
      event.preventDefault();
      requestOrWarn(dialog, password, dialog.dataset.studentUrl, function (payload) { handlePending(dialog, payload); });
    });

    var external = qs(dialog, '[data-external-form]');
    if (external) external.addEventListener('submit', function (event) {
      event.preventDefault();
      requestOrWarn(dialog, external, dialog.dataset.externalUrl, function (payload) { handlePending(dialog, payload); });
    });

    var verify = qs(dialog, '[data-verify-form]');
    if (verify) verify.addEventListener('submit', function (event) {
      event.preventDefault();
      if (!dialog.dataset.verifyUrl) return showError(dialog, 'Verification session is missing. Start the registration again.');
      requestOrWarn(dialog, verify, dialog.dataset.verifyUrl, function (payload) { complete(dialog, payload); });
    });

    var resend = qs(dialog, '[data-resend]');
    if (resend) resend.addEventListener('click', function () {
      if (!dialog.dataset.resendUrl) return showError(dialog, 'Verification session is missing. Start the registration again.');
      resend.disabled = true;
      var data = new FormData();
      data.append('csrfmiddlewaretoken', csrf(dialog));
      post(dialog.dataset.resendUrl, data, dialog).then(function (payload) {
        if (!payload.ok) return showError(dialog, payload.error);
        var note = qs(dialog, '[data-inline-note]');
        if (note) { note.textContent = payload.message || 'A new code was sent.'; note.hidden = false; }
      }).catch(function () { showError(dialog, 'Could not resend the code.'); }).finally(function () { resend.disabled = false; });
    });

    var override = qs(dialog, '[data-email-warning-override]');
    if (override) override.addEventListener('click', function () {
      var form = dialog._emailRetryForm;
      if (!form) return;
      var field = qs(form, '[data-email-override]');
      if (field) field.value = '1';
      hideWarning(dialog);
      form.requestSubmit();
    });
    var dismiss = qs(dialog, '[data-email-warning-dismiss]');
    if (dismiss) dismiss.addEventListener('click', function () { hideWarning(dialog); });
  }

  document.addEventListener('DOMContentLoaded', function () {
    qsa(document, '[data-mock-register-dialog]').forEach(setup);
  });
})();
