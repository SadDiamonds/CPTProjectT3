document.addEventListener("DOMContentLoaded", () => {
  const password = document.getElementById("password");
  const confirm = document.getElementById("confirm_password");
  const checklist = document.getElementById("passwordChecklist");

  // checklist items
  const lengthItem = document.getElementById("length");
  const uppercaseItem = document.getElementById("uppercase");
  const symbolItem = document.getElementById("symbol");
  const matchItem = document.getElementById("match");

  if (!password || !confirm || !checklist) return; // safety

  const symbolRegex = /[!@#$%^&*(),.?":{}|<>]/;
  const uppercaseRegex = /[A-Z]/;

  function showChecklist() {
    checklist.classList.remove("hidden");
  }

  function hideChecklist() {
    checklist.classList.add("hidden");
  }

  // Validation function — updates classes on each rule
  function validate() {
    const p = password.value;
    const c = confirm.value;

    if (p.length >= 8) {
      lengthItem.classList.add("valid");
      lengthItem.classList.remove("invalid");
    } else {
      lengthItem.classList.add("invalid");
      lengthItem.classList.remove("valid");
    }

    if (uppercaseRegex.test(p)) {
      uppercaseItem.classList.add("valid");
      uppercaseItem.classList.remove("invalid");
    } else {
      uppercaseItem.classList.add("invalid");
      uppercaseItem.classList.remove("valid");
    }

    if (symbolRegex.test(p)) {
      symbolItem.classList.add("valid");
      symbolItem.classList.remove("invalid");
    } else {
      symbolItem.classList.add("invalid");
      symbolItem.classList.remove("valid");
    }

    if (p && c && p === c) {
      matchItem.classList.add("valid");
      matchItem.classList.remove("invalid");
    } else {
      matchItem.classList.add("invalid");
      matchItem.classList.remove("valid");
    }
  }

  // show checklist when either field receives focus
  password.addEventListener("focus", showChecklist);
  confirm.addEventListener("focus", showChecklist);

  // hide checklist if focus leaves both fields
  // use a tiny timeout so focus switches from password->confirm don't hide it
  password.addEventListener("blur", () => {
    setTimeout(() => {
      const active = document.activeElement;
      if (active !== password && active !== confirm) hideChecklist();
    }, 0);
  });
  confirm.addEventListener("blur", () => {
    setTimeout(() => {
      const active = document.activeElement;
      if (active !== password && active !== confirm) hideChecklist();
    }, 0);
  });

  // live validation while typing
  password.addEventListener("input", validate);
  confirm.addEventListener("input", validate);

  // initialize state: hidden until focus
  hideChecklist();
  validate();
});
