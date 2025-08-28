const steps = document.querySelectorAll(".form-step");
let currentStep = 0;

function showNextStep() {
  if (currentStep + 1 < steps.length) {
    currentStep++;
    steps[currentStep].classList.add("step-active");
    // Scroll to newly added step
    steps[currentStep].scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

// Reveal next step when current input is filled
steps.forEach((step, idx) => {
  const inputs = step.querySelectorAll("input, select");
  inputs.forEach(input => {
    input.addEventListener("input", () => {
      let filled = Array.from(inputs).every(i => i.value.trim() !== "");
      if (filled && idx === currentStep) {
        showNextStep();
      }
    });
  });
});

// Password validation
const password = document.getElementById("password");
const confirm = document.getElementById("confirm_password");
const lengthCheck = document.getElementById("length");
const uppercaseCheck = document.getElementById("uppercase");
const symbolCheck = document.getElementById("symbol");
const matchCheck = document.getElementById("match");

function validatePassword() {
  const pwd = password.value;

  if (pwd.length >= 8) lengthCheck.classList.add("valid"); else lengthCheck.classList.remove("valid");
  if (/[A-Z]/.test(pwd)) uppercaseCheck.classList.add("valid"); else uppercaseCheck.classList.remove("valid");
  if (/[!@#$%^&*(),.?":{}|<>]/.test(pwd)) symbolCheck.classList.add("valid"); else symbolCheck.classList.remove("valid");
  if (pwd === confirm.value && pwd !== "") matchCheck.classList.add("valid"); else matchCheck.classList.remove("valid");
}

password.addEventListener("input", validatePassword);
confirm.addEventListener("input", validatePassword);
