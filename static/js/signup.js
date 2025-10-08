document.addEventListener("DOMContentLoaded", () => {
  const password = document.getElementById("password");
  const confirm = document.getElementById("confirm_password");
  const checklist = document.getElementById("passwordChecklist");

  // checklist items
  const lengthItem = document.getElementById("length");
  const uppercaseItem = document.getElementById("uppercase");
  const symbolItem = document.getElementById("symbol");
  const matchItem = document.getElementById("match");

  const roleSelect = document.getElementById("role");
  const recipientCategories = document.getElementById("recipientCategories");

  // submit button (will exist on signup and reset forms)
  const submitBtn = document.querySelector("form.auth-form button[type='submit']");

  if (!password || !confirm || !checklist) return; // safety

  const symbolRegex = /[!@#$%^&*(),.?":{}|<>]/;
  const uppercaseRegex = /[A-Z]/;

  function showChecklist() {
    checklist.classList.add("show");
  }

  function hideChecklist() {
    checklist.classList.remove("show");
  }

  // Validation function — updates classes on each rule + submit state
  function validate() {
    const p = password.value;
    const c = confirm.value;

    let valid = true;

    // Length
    if (p.length >= 8) {
      lengthItem.classList.add("valid");
      lengthItem.classList.remove("invalid");
    } else {
      lengthItem.classList.add("invalid");
      lengthItem.classList.remove("valid");
      valid = false;
    }

    // Uppercase
    if (uppercaseRegex.test(p)) {
      uppercaseItem.classList.add("valid");
      uppercaseItem.classList.remove("invalid");
    } else {
      uppercaseItem.classList.add("invalid");
      uppercaseItem.classList.remove("valid");
      valid = false;
    }

    // Symbol
    if (symbolRegex.test(p)) {
      symbolItem.classList.add("valid");
      symbolItem.classList.remove("invalid");
    } else {
      symbolItem.classList.add("invalid");
      symbolItem.classList.remove("valid");
      valid = false;
    }

    // Match
    if (p && c && p === c) {
      matchItem.classList.add("valid");
      matchItem.classList.remove("invalid");
    } else {
      matchItem.classList.add("invalid");
      matchItem.classList.remove("valid");
      valid = false;
    }

    // Enable/disable submit button
    if (submitBtn) {
      submitBtn.disabled = !valid;
    }
  }

  // show checklist when either field receives focus
  password.addEventListener("focus", showChecklist);
  confirm.addEventListener("focus", showChecklist);

  // hide checklist if focus leaves both fields
  password.addEventListener("blur", () => {
    setTimeout(() => {
      if (document.activeElement !== password && document.activeElement !== confirm) hideChecklist();
    }, 50);
  });
  confirm.addEventListener("blur", () => {
    setTimeout(() => {
      if (document.activeElement !== password && document.activeElement !== confirm) hideChecklist();
    }, 50);
  });

  // live validation while typing
  password.addEventListener("input", validate);
  confirm.addEventListener("input", validate);

  if (roleSelect && recipientCategories) {
    roleSelect.addEventListener("change", () => {
      if (roleSelect.value === "Recipient") {
        recipientCategories.classList.remove("hidden");
      } else {
        recipientCategories.classList.add("hidden");
      }
    });
  }

  // initialize state: hidden until focus, disabled submit
  hideChecklist();
  validate();
});
